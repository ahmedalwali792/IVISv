import time
from typing import Optional

from ivis_logging import setup_logging

logger = setup_logging("ingestion")


class Heartbeat:
    def __init__(self, stream_id, camera_id=None, interval_sec=5.0):
        self.stream_id = stream_id
        self.camera_id = camera_id
        self.last_beat = 0
        self.interval = max(0.5, float(interval_sec))

    def tick(self, status: str = "ok", reason: Optional[str] = None):
        now = time.time()
        if now - self.last_beat > self.interval:
            logger.info(
                "ingestion.heartbeat",
                extra={
                    "stream_id": self.stream_id,
                    "camera_id": self.camera_id,
                    "status": status,
                    "reason": reason,
                },
            )
            self.last_beat = now
