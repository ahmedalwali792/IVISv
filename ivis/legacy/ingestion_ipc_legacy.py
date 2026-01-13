"""
Legacy ingestion IPC transports (kept for reference and optional backwards compatibility).
This module is intentionally isolated under `ivis.legacy` and is NOT part of the
default production path. Use Redis Streams (`RedisPublisher`) in `ingestion.ipc`
for production.
"""
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
