import time
from typing import Optional

from ivis.common.time_utils import wall_clock_ms
from ivis_logging import setup_logging

logger = setup_logging("ingestion")


class Heartbeat:
    def __init__(self, stream_id, camera_id=None, redis_url=None, stream="ivis:health", interval_sec=5.0):
        self.stream_id = stream_id
        self.camera_id = camera_id
        self.last_beat = 0
        self.interval = max(0.5, float(interval_sec))
        self.stream = stream
        self._redis = None
        self._redis_error = None
        if redis_url:
            try:
                import redis
                self._redis = redis.Redis.from_url(redis_url)
            except Exception as exc:
                self._redis_error = exc
                logger.warning("Health heartbeat Redis disabled: %s", exc)

    def _publish(self, status: str, reason: Optional[str]):
        if not self._redis or not self.stream:
            return
        payload = {
            "service": "ingestion",
            "stream_id": self.stream_id,
            "camera_id": self.camera_id or "",
            "status": status,
            "reason": reason or "",
            "timestamp_ms": wall_clock_ms(),
        }
        try:
            self._redis.xadd(self.stream, payload)
        except Exception as exc:
            if self._redis_error is None:
                logger.warning("Health heartbeat publish failed: %s", exc)
                self._redis_error = exc

    def tick(self, status: str = "ok", reason: Optional[str] = None):
        now = time.time()
        if now - self.last_beat > self.interval:
            logger.info("ingestion.heartbeat", extra={"stream_id": self.stream_id})
            self._publish(status, reason)
            self.last_beat = now
