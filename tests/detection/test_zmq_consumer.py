import importlib
import sys
import types


def _set_required_env(monkeypatch):
    monkeypatch.setenv("MODEL_NAME", "test-model")
    monkeypatch.setenv("MODEL_VERSION", "0")
    monkeypatch.setenv("MODEL_HASH", "hash")
    monkeypatch.setenv("MODEL_PATH", "path")


def test_zmq_consumer_connect_idempotent(monkeypatch):
    _set_required_env(monkeypatch)

    class FakeSocket:
        def __init__(self):
            self.connect_calls = []
            self.opts = []

        def setsockopt(self, opt, value):
            self.opts.append((opt, value))

        def connect(self, endpoint):
            self.connect_calls.append(endpoint)

        def close(self):
            return None

    fake_socket = FakeSocket()

    class FakeContext:
        def socket(self, sock_type):
            return fake_socket

    class FakeContextWrapper:
        @staticmethod
        def instance():
            return FakeContext()

    fake_zmq = types.SimpleNamespace(
        SUB=1,
        SUBSCRIBE=2,
        RCVHWM=3,
        LINGER=4,
        CONFLATE=5,
        Context=FakeContextWrapper,
    )

    monkeypatch.setitem(sys.modules, "zmq", fake_zmq)

    if "detection.config" in sys.modules:
        importlib.reload(sys.modules["detection.config"])
    if "detection.ingest.consumer" in sys.modules:
        consumer = importlib.reload(sys.modules["detection.ingest.consumer"])
    else:
        import detection.ingest.consumer as consumer

    sub = consumer.ZmqFrameConsumer("tcp://example:5555")
    sub.connect()
    sub.connect()

    assert fake_socket.connect_calls == ["tcp://example:5555"]
