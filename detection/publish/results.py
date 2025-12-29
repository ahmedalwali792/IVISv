# [2025-12-29] detection/publish/results.py
import json
from detection.config import Config
from detection.errors.fatal import FatalError

class ResultPublisher:
    """
    Logic Publisher for Results.
    """
    def __init__(self, producer):
        self.producer = producer

    def publish(self, result: dict):
        result["model"] = {"name": Config.MODEL_NAME}
        try:
            payload = json.dumps(result).encode('utf-8')
            # Blind Publish
            self.producer.publish(Config.OUTPUT_TOPIC, payload)
            print(f"[RESULT] Sent result for {result['frame_id'][:8]}")
        except Exception as e:
            raise FatalError(f"Publish failed: {e}")