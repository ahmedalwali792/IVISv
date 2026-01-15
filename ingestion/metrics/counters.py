# ------------------------------------------------------------------------------
# FILE: ingestion/metrics/counters.py
# ------------------------------------------------------------------------------
class Metrics:
    def __init__(self):
        self.frames_captured = 0
        self.dropped_fps = 0       
        self.dropped_corrupt = 0   
        self.dropped_pts = 0       
        self.frames_processed = 0  
        self.write_failures = 0
        # per-reason drops
        self.frames_dropped_by_reason = {}

    def inc_captured(self): self.frames_captured += 1
    def inc_dropped_fps(self): self.dropped_fps += 1
    def inc_dropped_corrupt(self): self.dropped_corrupt += 1
    def inc_dropped_pts(self): self.dropped_pts += 1
    def inc_processed(self): self.frames_processed += 1
    def inc_write_failure(self): self.write_failures += 1
    def inc_dropped_reason(self, reason: str):
        if not isinstance(reason, str) or not reason:
            reason = "unspecified"
        self.frames_dropped_by_reason[reason] = self.frames_dropped_by_reason.get(reason, 0) + 1
