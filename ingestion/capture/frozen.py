# FILE: ingestion/capture/frozen.py
# ------------------------------------------------------------------------------
from typing import Optional, Union

from ivis.common.time_utils import monotonic_ms


class FrozenStreamDetector:
    def __init__(
        self,
        no_frame_timeout_sec: float,
        repeat_hash_count: int,
        pts_stuck_count: int,
        timestamp_stuck_count: int,
    ):
        self.no_frame_timeout_ms = max(0.0, float(no_frame_timeout_sec)) * 1000.0
        self.repeat_hash_count = max(0, int(repeat_hash_count))
        self.pts_stuck_count = max(0, int(pts_stuck_count))
        self.timestamp_stuck_count = max(0, int(timestamp_stuck_count))
        self.reset()

    def reset(self) -> None:
        self.last_frame_mono = None
        self.last_hash = None
        self.repeat_hash_runs = 0
        self.last_pts = None
        self.pts_stuck_runs = 0
        self.last_timestamp_ms = None
        self.timestamp_stuck_runs = 0

    def note_frame(
        self,
        pts: Optional[Union[float, int]],
        timestamp_ms: Optional[int],
        fingerprint: Optional[str],
        mono_ms: Optional[int],
    ) -> None:
        self.last_frame_mono = int(mono_ms) if mono_ms is not None else monotonic_ms()

        if fingerprint:
            if self.last_hash == fingerprint:
                self.repeat_hash_runs += 1
            else:
                self.repeat_hash_runs = 0
                self.last_hash = fingerprint

        if pts is not None:
            if self.last_pts is not None and pts <= self.last_pts:
                self.pts_stuck_runs += 1
            else:
                self.pts_stuck_runs = 0
                self.last_pts = pts

        if timestamp_ms is not None:
            if self.last_timestamp_ms is not None and timestamp_ms <= self.last_timestamp_ms:
                self.timestamp_stuck_runs += 1
            else:
                self.timestamp_stuck_runs = 0
                self.last_timestamp_ms = timestamp_ms

    def check(self, now_mono_ms: Optional[int] = None) -> Optional[str]:
        now = int(now_mono_ms) if now_mono_ms is not None else monotonic_ms()
        if self.last_frame_mono is not None and self.no_frame_timeout_ms > 0:
            if (now - self.last_frame_mono) > self.no_frame_timeout_ms:
                return "no_frames"
        if self.repeat_hash_count and self.repeat_hash_runs >= self.repeat_hash_count:
            return "repeat_hash"
        if self.pts_stuck_count and self.pts_stuck_runs >= self.pts_stuck_count:
            return "pts_stuck"
        if self.timestamp_stuck_count and self.timestamp_stuck_runs >= self.timestamp_stuck_count:
            return "timestamp_stuck"
        return None
