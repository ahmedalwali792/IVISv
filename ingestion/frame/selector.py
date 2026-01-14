# FILE: ingestion/frame/selector.py
# ------------------------------------------------------------------------------
import time
from typing import Optional


class Selector:
    def __init__(self, target_fps, mode: str = "clock"):
        self._base_target_fps = max(1.0, float(target_fps))
        self._lag_cap_fps = None
        self.target_fps = self._base_target_fps
        self.frame_duration_ms = (1.0 / self.target_fps) * 1000.0
        self.last_pts = -1.0
        self.last_emit_ms = -1.0
        self.mode = mode

    def allow(self, pts):
        if self.mode == "pts" and pts > 0:
            if self.last_pts < 0:
                self.last_pts = pts
                return True
            if pts <= self.last_pts:
                return False
            delta = pts - self.last_pts
            if delta >= self.frame_duration_ms:
                self.last_pts = pts
                return True
            return False

        now_ms = time.perf_counter() * 1000.0
        if self.last_emit_ms < 0:
            self.last_emit_ms = now_ms
            return True
        if (now_ms - self.last_emit_ms) >= self.frame_duration_ms:
            self.last_emit_ms = now_ms
            if pts > 0:
                self.last_pts = pts
            return True
        return False

    def set_target_fps(self, fps: float):
        if fps <= 0:
            return
        self._base_target_fps = float(fps)
        self._apply_effective_fps()

    def set_lag_cap(self, fps: Optional[float]):
        if fps is None:
            self._lag_cap_fps = None
        else:
            self._lag_cap_fps = max(1.0, float(fps))
        self._apply_effective_fps()

    def _apply_effective_fps(self) -> None:
        effective = self._base_target_fps
        if self._lag_cap_fps is not None:
            effective = min(effective, self._lag_cap_fps)
        effective = max(1.0, float(effective))
        self.target_fps = effective
        self.frame_duration_ms = (1.0 / effective) * 1000.0
