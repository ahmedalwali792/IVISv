# FILE: detection/metrics/counters.py
# ------------------------------------------------------------------------------
class Metrics:
    def __init__(self):
        self.frames_received = 0
        self.frames_processed = 0
        self.frames_dropped = 0
        # keyed by reason string, e.g. {"bad_dtype": 3}
        self.frames_dropped_by_reason = {}
        self.fatal_crashes = 0
        self.last_inference_latency_ms = 0.0

    def inc_received(self): self.frames_received += 1
    def inc_processed(self): self.frames_processed += 1
    def inc_dropped(self): self.frames_dropped += 1
    def inc_dropped_reason(self, reason: str):
        """Increment dropped-frames counter with a reason label.

        This also increments the aggregate `frames_dropped`.
        """
        if not isinstance(reason, str) or not reason:
            reason = "unspecified"
        self.frames_dropped += 1
        self.frames_dropped_by_reason[reason] = self.frames_dropped_by_reason.get(reason, 0) + 1
    def log_latency(self, ms: float): self.last_inference_latency_ms = ms

metrics = Metrics()
