# FILE: ingestion/frame/selector.py
# ------------------------------------------------------------------------------
class Selector:
    def __init__(self, target_fps):
        self.target_fps = target_fps
        self.frame_duration_ms = (1.0 / target_fps) * 1000
        self.last_pts = -1.0

    def allow(self, pts):
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
