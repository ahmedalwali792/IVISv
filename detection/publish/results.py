# FILE: detection/publish/results.py
# ------------------------------------------------------------------------------
import json

from detection.config import Config
from ingestion.errors.fatal import FatalError

class ResultPublisher:
    def publish(self, result: dict):
        result["model"] = {
            "name": Config.MODEL_NAME,
            "version": Config.MODEL_VERSION,
            "hash": Config.MODEL_HASH,
        }

        try:
            payload = json.dumps(result)
            print(f"[RESULT] {payload}")  
        except Exception as e:
            raise FatalError("Publish failed", context={"error": str(e)})
