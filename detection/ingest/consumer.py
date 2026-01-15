# FILE: detection/ingest/consumer.py
# ------------------------------------------------------------------------------
import json
import socket
import logging

from detection.config import Config
from detection.errors.fatal import FatalError
import ivis_metrics


_logger = logging.getLogger("detection")
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
        ivis_metrics.service_errors_total.labels(service="detection", reason=reason).inc()
    except Exception as metric_exc:
        _log_once(f"{reason}_metric", "Failed to record service error metric", metric_exc)


class TcpFrameConsumer:
    def __init__(self, host="localhost", port=5555):
        self.address = (host, port)
        self.sock = None
        self.buffer = ""

    def connect(self):
        if not self.sock:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(5.0)
                self.sock.connect(self.address)
                self.sock.settimeout(None)
                print(f"[DETECTION] Connected to Bus at {self.address}")
            except Exception as e:
                raise FatalError(f"Failed to connect to Bus at {self.address}", context={"error": str(e)})

    def __iter__(self):
        self.connect()
        while True:
            try:
                data = self.sock.recv(4096)
                if not data:
                    raise FatalError("Bus connection lost (EOF)")

                self.buffer += data.decode("utf-8")

                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    if line.strip():
                        try:
                            contract = json.loads(line)
                            yield contract
                        except json.JSONDecodeError:
                            print("[Warn] Received malformed JSON from Bus")
                            continue
            except FatalError:
                raise
            except Exception as e:
                raise FatalError("Bus Consumer Error", context={"error": str(e)})


class ZmqFrameConsumer:
    def __init__(self, endpoint: str):
        try:
            import zmq
        except Exception as exc:
            raise FatalError("Missing ZeroMQ dependency", context={"error": str(exc)}) from exc
        self.zmq = zmq
        self.endpoint = endpoint
        self.socket = None

    def connect(self):
        ctx = self.zmq.Context.instance()
        self.socket = ctx.socket(self.zmq.SUB)
        self.socket.connect(self.endpoint)
        self.socket.setsockopt(self.zmq.SUBSCRIBE, b"")
        try:
            self.socket.setsockopt(self.zmq.CONFLATE, 1)
            print("[DETECTION] ZMQ CONFLATE enabled (processing latest frames only)")
        except Exception:
            print("[DETECTION] ZMQ CONFLATE not supported (ignoring)")
        print(f"[DETECTION] ZMQ SUB connected to {self.endpoint}")

    def __iter__(self):
        if not self.socket:
            self.connect()
        while True:
            try:
                payload = self.socket.recv()
                contract = json.loads(payload.decode("utf-8"))
                yield contract
            except Exception as e:
                raise FatalError("ZMQ Consumer Error", context={"error": str(e)})


class FrameConsumer:
    """
    Stage 2 Fix: No internal retry loops on startup. Fail Fast.
    """

    def __init__(self, host="localhost", port=5555):
        transport = Config.BUS_TRANSPORT.lower()
        if transport == "zmq":
            self._impl = ZmqFrameConsumer(Config.ZMQ_SUB_ENDPOINT)
        elif transport == "tcp":
            self._impl = TcpFrameConsumer(host=host, port=port)
        else:
            raise FatalError(f"Unsupported BUS_TRANSPORT: {Config.BUS_TRANSPORT}")

    def connect(self):
        if hasattr(self._impl, "connect"):
            return self._impl.connect()
        return None

    def __iter__(self):
        return iter(self._impl)
