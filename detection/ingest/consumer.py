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


class RedisFrameConsumer:
    def __init__(self, url: str, stream: str, group: str, consumer: str):
        try:
            import redis
        except Exception as exc:
            raise FatalError("Missing Redis dependency", context={"error": str(exc)}) from exc
        self.redis = redis.Redis.from_url(url)
        self._redis_error = getattr(redis.exceptions, "RedisError", Exception)
        self._redis_response_error = getattr(redis.exceptions, "ResponseError", Exception)
        self.stream = stream
        self.group = group
        self.consumer = consumer
        self._ensure_group()

    def _ensure_group(self):
        try:
            self.redis.xgroup_create(self.stream, self.group, id="0-0", mkstream=True)
        except self._redis_response_error as exc:
            if "BUSYGROUP" not in str(exc).upper():
                _record_issue("redis_group_create_failed", "Redis group create failed", exc)
                raise FatalError("Redis consumer group create failed", context={"error": str(exc)})
        except self._redis_error as exc:
            _record_issue("redis_group_create_failed", "Redis group create failed", exc)
            raise FatalError("Redis consumer group create failed", context={"error": str(exc)})

    def __iter__(self):
        while True:
            try:
                resp = self.redis.xreadgroup(
                    self.group,
                    self.consumer,
                    {self.stream: ">"},
                    count=1,
                    block=5000,
                )
                if not resp:
                    continue
                _, messages = resp[0]
                msg_id, fields = messages[0]
                data = fields.get(b"payload") or fields.get("payload")
                if data is None:
                    self.redis.xack(self.stream, self.group, msg_id)
                    continue
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                contract = json.loads(data)
                self.redis.xack(self.stream, self.group, msg_id)
                yield contract
            except Exception as e:
                raise FatalError("Redis Consumer Error", context={"error": str(e)})


class RedisPubSubConsumer:
    def __init__(self, url: str, channel: str):
        try:
            import redis
        except Exception as exc:
            raise FatalError("Missing Redis dependency", context={"error": str(exc)}) from exc
        self.redis = redis.Redis.from_url(url)
        self.channel = channel
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(self.channel)

    def __iter__(self):
        while True:
            try:
                message = self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not message:
                    continue
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                latest = data
                while True:
                    more = self.pubsub.get_message(ignore_subscribe_messages=True, timeout=0.0)
                    if not more:
                        break
                    more_data = more.get("data")
                    if isinstance(more_data, bytes):
                        more_data = more_data.decode("utf-8")
                    latest = more_data
                contract = json.loads(latest)
                yield contract
            except Exception as e:
                raise FatalError("Redis PubSub Consumer Error", context={"error": str(e)})


class FrameConsumer:
    """
    Stage 2 Fix: No internal retry loops on startup. Fail Fast.
    """

    def __init__(self, host="localhost", port=5555):
        transport = Config.BUS_TRANSPORT.lower()
        # Production default: Redis Streams. Legacy transports live under ivis.legacy
        if transport == "redis":
            # Use XREADGROUP consumer for streams by default
            if Config.REDIS_MODE.lower() == "pubsub":
                # Rare fallback: pubsub mode (legacy)
                self._impl = RedisPubSubConsumer(Config.REDIS_URL, Config.REDIS_CHANNEL)
            else:
                self._impl = RedisFrameConsumer(
                    Config.REDIS_URL,
                    Config.REDIS_STREAM,
                    Config.REDIS_GROUP,
                    Config.REDIS_CONSUMER,
                )
        else:
            # Non-Redis transports are considered legacy; import them from ivis.legacy
            try:
                from ivis.legacy.detection_ingest_consumer_legacy import (
                    ZmqFrameConsumer,
                    TcpFrameConsumer,
                    RedisPubSubConsumer,
                )
            except Exception:
                raise FatalError("Legacy transport support unavailable")

            if transport == "zmq":
                self._impl = ZmqFrameConsumer(Config.ZMQ_SUB_ENDPOINT)
            elif transport == "tcp":
                self._impl = TcpFrameConsumer(host=host, port=port)
            elif transport == "pubsub":
                self._impl = RedisPubSubConsumer(Config.REDIS_URL, Config.REDIS_CHANNEL)
            else:
                raise FatalError(f"Unsupported BUS_TRANSPORT: {Config.BUS_TRANSPORT}")

    def __iter__(self):
        return iter(self._impl)
