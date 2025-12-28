
# FILE: ingestion/runtime.py
import signal

class Runtime:
    def __init__(self):
        self.is_running = True
        self._setup_signals()

    def _setup_signals(self):
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

    def _handle_exit(self, signum, frame):
        print(f"\n[Runtime] Received signal {signum}. Stopping loop...")
        self.is_running = False

    def should_continue(self):
        return self.is_running

    def shutdown(self):
        print("[Runtime] Shutdown sequence complete.")
