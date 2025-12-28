# FILE: detection/ingest/consumer.py
# ------------------------------------------------------------------------------
import socket
import json
import time

from detection.errors.fatal import FatalError

class FrameConsumer:
    """
    Stage 2 Fix: No internal retry loops on startup. Fail Fast.
    """
    def __init__(self, host="localhost", port=5555):
        self.address = (host, port)
        self.sock = None
        self.buffer = ""

    def connect(self):
        if not self.sock:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(5.0)
                self.sock.connect(self.address)
                self.sock.settimeout(None)
                print(f"[DETECTION] Connected to Bus at {self.address}")
            except Exception as e:
                # ❌ No Retry
                raise FatalError(f"Failed to connect to Bus at {self.address}", context={"error": str(e)})

    def __iter__(self):
        self.connect()
        while True:
            try:
                data = self.sock.recv(4096)
                if not data:
                    raise FatalError("Bus connection lost (EOF)")
                
                self.buffer += data.decode('utf-8')
                
                while "\n" in self.buffer:
                    line, self.buffer = self.buffer.split("\n", 1)
                    if line.strip():
                        try:
                            contract = json.loads(line)
                            yield contract
                        except json.JSONDecodeError:
                            print("[Warn] Received malformed JSON from Bus")
                            continue
            except FatalError:
                raise
            except Exception as e:
                raise FatalError("Bus Consumer Error", context={"error": str(e)})
