# FILE: ingestion/recording/buffer.py
# ------------------------------------------------------------------------------
from collections import deque

import cv2


class RecordingBuffer:
    def __init__(self, max_seconds: float, max_frames: int, jpeg_quality: int = 85):
        self.max_seconds = max(0.0, float(max_seconds))
        self.max_frames = max(1, int(max_frames))
        self.jpeg_quality = max(1, min(100, int(jpeg_quality)))
        self._frames = deque(maxlen=self.max_frames)
        self.drops = 0

    def _prune_by_time(self, now_ms: int) -> None:
        if self.max_seconds <= 0:
            return
        cutoff = now_ms - int(self.max_seconds * 1000.0)
        while self._frames and self._frames[0][0] < cutoff:
            self._frames.popleft()

    def add_frame(self, frame_bgr, timestamp_ms: int) -> bool:
        params = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
        ok, jpeg = cv2.imencode(".jpg", frame_bgr, params)
        if not ok:
            return False
        if len(self._frames) == self._frames.maxlen:
            self.drops += 1
        self._frames.append((int(timestamp_ms), jpeg.tobytes()))
        self._prune_by_time(int(timestamp_ms))
        return True

    def get_clip_frames(self, start_ms: int, end_ms: int):
        start = int(start_ms)
        end = int(end_ms)
        return [payload for ts, payload in self._frames if start <= ts <= end]

    def size(self) -> int:
        return len(self._frames)
