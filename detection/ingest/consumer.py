# [2025-12-29] detection/ingest/consumer.py
import json
import time
from detection.errors.fatal import FatalError

class FrameConsumer:
    """
    Business Logic Consumer.
    """
    def __init__(self, transport_consumer):
        self.consumer = transport_consumer # Injected Dependency

    def __iter__(self):
        while True:
            try:
                # Blind Poll
                data = self.consumer.poll(timeout=1.0)
                if data is None:
                    continue # Idle loop
                
                # Logic: Parse & Validate JSON Structure
                try:
                    contract = json.loads(data.decode('utf-8'))
                    yield contract
                except json.JSONDecodeError:
                    print("[Warn] Received malformed JSON")
                    continue
                    
            except Exception as e:
                raise FatalError("Consumer Logic Error", context={"error": str(e)})