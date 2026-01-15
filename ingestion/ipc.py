# FILE: ingestion/ipc.py
# ------------------------------------------------------------------------------
import json
import socket
import logging

from ingestion.memory.ref import MemoryReference
from ivis.common.contracts.frame_contract import FrameContractV1, FrameMemoryRef
import ivis_metrics


_logger = logging.getLogger("ingestion")
_warned = set()


def _log_once(key: str, message: str, exc: Exception = None) -> None:
    if key in _warned:
        return
    _warned.add(key)
    if exc is not None:
        _logger.warning("%s: %s", message, exc)
    else:
        _logger.warning("%s", message)


def _record_issue(reason: str, message: str, exc: Exception = None) -> None:
    _log_once(reason, message, exc)
    try:
        ivis_metrics.service_errors_total.labels(service="ingestion", reason=reason).inc()
    except Exception as metric_exc:
        _log_once(f"{reason}_metric", "Failed to record service error metric", metric_exc)


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
        except (OSError, ConnectionError) as exc:
            _record_issue("socket_connect_failed", "Socket connect failed", exc)
            self.sock = None

    def publish(self, frame_identity, packet_timestamp_ms, packet_mono_ms, memory_ref, roi_meta=None):
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
            roi_meta=roi_meta,
        )
        payload = json.dumps(contract) + "\n"

        if self.sock:
            try:
                self.sock.sendall(payload.encode())
                return True
            except (OSError, ConnectionError) as exc:
                _record_issue("socket_send_failed", "Socket send failed", exc)
                _logger.warning("[PUB] Transport lost. Dropping msg.")
                self.sock.close()
                self._connect()
                return False
        self._connect()
        return False


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
        self.socket.bind(self.endpoint)

    def publish(self, frame_identity, packet_timestamp_ms, packet_mono_ms, memory_ref, roi_meta=None):
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
            roi_meta=roi_meta,
        )
        payload = json.dumps(contract).encode("utf-8")
        try:
            self.socket.send(payload)
            return True
        except Exception as exc:
            _record_issue("zmq_send_failed", "ZMQ send failed", exc)
            return False


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
    roi_meta=None,
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
    payload = contract.to_dict()
    if roi_meta:
        payload["roi"] = roi_meta
    return payload


def get_publisher(config):
    transport = getattr(config, "bus_transport", "zmq").lower()
    if transport == "zmq":
        try:
            from ivis.legacy.ingestion_ipc_legacy import ZmqPublisher as LegacyZmqPublisher

            return LegacyZmqPublisher(config, getattr(config, "zmq_pub_endpoint", "tcp://localhost:5555"))
        except Exception as exc:
            _record_issue("legacy_zmq_import_failed", "Legacy ZMQ publisher import failed; falling back", exc)
            # fallback to module-local ZmqPublisher if legacy package missing
            return ZmqPublisher(config, getattr(config, "zmq_pub_endpoint", "tcp://localhost:5555"))
    # Legacy TCP publisher (socket) - co-locate under ivis.legacy when used.
    try:
        from ivis.legacy.ingestion_ipc_legacy import SocketPublisher as LegacySocketPublisher

        return LegacySocketPublisher(config)
    except Exception as exc:
        _record_issue("legacy_socket_import_failed", "Legacy Socket publisher import failed; falling back", exc)
        return SocketPublisher(config)
