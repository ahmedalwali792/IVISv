# FILE: memory/metrics/counters.py
# ------------------------------------------------------------------------------
class Metrics:
    _instance = None
    def __init__(self):
        self.writes_ok = 0
        self.writes_failed = 0
        self.reads_ok = 0
        self.reads_miss = 0
        self.evictions = 0 

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def inc_write_ok(self): self.writes_ok += 1
    def inc_write_fail(self): self.writes_failed += 1
    def inc_read_ok(self): self.reads_ok += 1
    def inc_read_miss(self): self.reads_miss += 1
    def snapshot(self):
        return {
            "writes_ok": self.writes_ok,
            "writes_failed": self.writes_failed,
            "reads_ok": self.reads_ok,
            "reads_miss": self.reads_miss,
            "evictions": self.evictions
        }
