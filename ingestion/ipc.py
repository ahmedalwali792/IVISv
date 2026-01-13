# FILE: ingestion/ipc.py
# ------------------------------------------------------------------------------
import json
import socket

from ingestion.memory.ref import MemoryReference
from ivis.common.contracts.frame_contract import FrameContractV1, FrameMemoryRef


class SocketPublisher:
    """
    TCP publisher (legacy).
    """

    def __init__(self, config, host="localhost", port=5555):
        self.stream_id = config.stream_id
        self.camera_id = config.camera_id
        self.frame_width = config.frame_width
        self.frame_height = config.frame_height
        self.frame_color = config.frame_color
        self.address = (host, port)
        self.sock = None
        self._connect()

    def _connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(self.address)
        except Exception:
            self.sock = None

    def publish(self, frame_identity, packet_timestamp_ms, packet_mono_ms, memory_ref):
        gen = getattr(memory_ref, "generation", 0)
        contract = _build_contract(
            self.stream_id,
            self.camera_id,
            frame_identity,
            packet_timestamp_ms,
            packet_mono_ms,
            memory_ref,
            gen,
            self.frame_width,
            self.frame_height,
            self.frame_color,
        )
        payload = json.dumps(contract) + "\n"

        if self.sock:
            try:
                self.sock.sendall(payload.encode())
            except Exception:
                print("[PUB] Transport lost. Dropping msg.")
                self.sock.close()
                self._connect()
        else:
            self._connect()


class ZmqPublisher:
    def __init__(self, config, endpoint: str):
        try:
            import zmq
        except Exception as exc:
            raise RuntimeError(f"Missing ZeroMQ dependency: {exc}") from exc

        self.stream_id = config.stream_id
        self.camera_id = config.camera_id
        self.frame_width = config.frame_width
        self.frame_height = config.frame_height
        self.frame_color = config.frame_color
        self.endpoint = endpoint
        self.zmq = zmq
        self.socket = self.zmq.Context.instance().socket(self.zmq.PUB)
        self.socket.connect(self.endpoint)

    def publish(self, frame_identity, packet_timestamp_ms, packet_mono_ms, memory_ref):
        gen = getattr(memory_ref, "generation", 0)
        contract = _build_contract(
            self.stream_id,
            self.camera_id,
            frame_identity,
            packet_timestamp_ms,
            packet_mono_ms,
            memory_ref,
            gen,
            self.frame_width,
            self.frame_height,
            self.frame_color,
        )
        payload = json.dumps(contract).encode("utf-8")
        self.socket.send(payload)


class RedisPublisher:
    def __init__(self, config, url: str, stream: str, mode: str, channel: str):
        try:
            import redis
        except Exception as exc:
            raise RuntimeError(f"Missing Redis dependency: {exc}") from exc

        self.stream_id = config.stream_id
        self.camera_id = config.camera_id
        self.frame_width = config.frame_width
        self.frame_height = config.frame_height
        self.frame_color = config.frame_color
        self.redis = redis.Redis.from_url(url)
        self.stream = stream
        self.mode = mode.lower()
        self.channel = channel
        # Max stream length before applying trimming/drop policy
        import os

        try:
            self.stream_maxlen = int(os.getenv("REDIS_STREAM_MAXLEN", "2000"))
        except Exception:
            self.stream_maxlen = 2000

    def publish(self, frame_identity, packet_timestamp_ms, packet_mono_ms, memory_ref):
        gen = getattr(memory_ref, "generation", 0)
        contract = _build_contract(
            self.stream_id,
            self.camera_id,
            frame_identity,
            packet_timestamp_ms,
            packet_mono_ms,
            memory_ref,
            gen,
            self.frame_width,
            self.frame_height,
            self.frame_color,
        )
        payload = json.dumps(contract)
        try:
            if self.mode == "pubsub":
                self.redis.publish(self.channel, payload)
                return True
            else:
                # Backpressure policy: if stream length exceeds threshold, trim or drop
                try:
                    xlen = int(self.redis.xlen(self.stream) or 0)
                except Exception:
                    xlen = 0

                # If stream very long, trim old entries first
                if xlen > (self.stream_maxlen * 2):
                    try:
                        # Trim to keep stream manageable
                        self.redis.xtrim(self.stream, maxlen=self.stream_maxlen, approximate=False)
                    except Exception:
                        pass

                # Recompute length and decide to drop if still above threshold
                try:
                    xlen = int(self.redis.xlen(self.stream) or 0)
                except Exception:
                    xlen = 0

                if xlen > self.stream_maxlen:
                    # Drop frame under keep-latest policy
                    return False

                # Otherwise append normally
                self.redis.xadd(self.stream, {"payload": payload})
                return True
        except Exception as exc:
            import logging
            logging.getLogger("ingestion").error("Redis publish failed: %s", exc)
            return False


class CompositePublisher:
    def __init__(self, publishers):
        self.publishers = publishers

    def publish(self, frame_identity, packet_timestamp_ms, packet_mono_ms, memory_ref):
        for publisher in self.publishers:
            publisher.publish(frame_identity, packet_timestamp_ms, packet_mono_ms, memory_ref)


def _build_contract(
    stream_id,
    camera_id,
    frame_identity,
    packet_timestamp_ms,
    packet_mono_ms,
    memory_ref,
    gen,
    frame_width,
    frame_height,
    frame_color,
):
    backend = getattr(memory_ref, "backend_type", "shm_ring_v1")
    memory = FrameMemoryRef(
        backend=backend,
        key=memory_ref.location,
        size=memory_ref.size,
        generation=gen,
    )
    output_color = "bgr"
    contract = FrameContractV1(
        contract_version=1,
        frame_id=frame_identity.frame_id,
        stream_id=stream_id,
        camera_id=camera_id,
        pts=frame_identity.pts,
        timestamp_ms=packet_timestamp_ms,
        mono_ms=packet_mono_ms,
        memory=memory,
        frame_width=frame_width,
        frame_height=frame_height,
        frame_channels=3,
        frame_dtype="uint8",
        frame_color_space=output_color,
    )
    return contract.to_dict()


def get_publisher(config):
    transport = getattr(config, "bus_transport", "redis").lower()
    if transport == "zmq":
        try:
            from ivis.legacy.ingestion_ipc_legacy import ZmqPublisher as LegacyZmqPublisher

            return LegacyZmqPublisher(config, getattr(config, "zmq_pub_endpoint", "tcp://localhost:5555"))
        except Exception:
            # fallback to module-local ZmqPublisher if legacy package missing
            return ZmqPublisher(config, getattr(config, "zmq_pub_endpoint", "tcp://localhost:5555"))
    if transport == "redis":
        return RedisPublisher(
            config,
            getattr(config, "redis_url", "redis://localhost:6379/0"),
            getattr(config, "redis_stream", "ivis:frames"),
            getattr(config, "redis_mode", "streams"),
                    getattr(config, "redis_channel", "ivis:frames"),
        )
    if transport == "both":
        return CompositePublisher(
            [
                ZmqPublisher(config, getattr(config, "zmq_pub_endpoint", "tcp://localhost:5555")),
                RedisPublisher(
                    config,
                    getattr(config, "redis_url", "redis://localhost:6379/0"),
                    getattr(config, "redis_stream", "ivis:frames"),
                    getattr(config, "redis_mode", "streams"),
                    getattr(config, "redis_channel", "ivis:frames"),
                ),
            ]
        )
    # Legacy TCP publisher (socket) - co-locate under ivis.legacy when used.
    try:
        from ivis.legacy.ingestion_ipc_legacy import SocketPublisher as LegacySocketPublisher

        return LegacySocketPublisher(config)
    except Exception:
        return SocketPublisher(config)
