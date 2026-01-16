# FILE: detection/runtime.py
# ------------------------------------------------------------------------------
import signal
import sys

class Runtime:
    def __init__(self):
        self.running = True
        self.stop_reason = ""
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

    def stop(self, signum, frame):
        print("\n[Detection] Stopping (Signal received)...")
        self.running = False
        self.stop_reason = "signal"

    def request_stop(self, reason: str = ""):
        self.running = False
        self.stop_reason = reason

    def should_continue(self) -> bool:
        return self.running
