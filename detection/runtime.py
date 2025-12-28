# FILE: detection/runtime.py
# ------------------------------------------------------------------------------
import signal
import sys

class Runtime:
    def __init__(self):
        self.running = True
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)

    def stop(self, signum, frame):
        print("\n[Detection] Stopping...")
        self.running = False
        sys.exit(0)
