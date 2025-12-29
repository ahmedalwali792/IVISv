# [2025-12-29] results/ingest/consumer.py
import json
import sys

class ResultConsumer:
    """
    Business Logic Consumer for Results.
    """
    def __init__(self, transport_consumer):
        self.consumer = transport_consumer

    def __iter__(self):
        while True:
            try:
                data = self.consumer.poll(timeout=1.0)
                if data is None: continue
                
                try:
                    msg = json.loads(data.decode('utf-8'))
                    if "detections" in msg and "frame_id" in msg:
                        yield msg
                except json.JSONDecodeError:
                    continue
            except Exception as e:
                print(f"FATAL: Result Consumer Error: {e}")
                sys.exit(1)