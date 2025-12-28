import time

class Heartbeat:
    def __init__(self, stream_id):
        self.stream_id = stream_id
        self.last_beat = 0
        self.interval = 5.0

    def tick(self):
        now = time.time()
        if now - self.last_beat > self.interval:
            print(f"[HEARTBEAT] Ingestion Alive | Stream: {self.stream_id}")
            self.last_beat = now