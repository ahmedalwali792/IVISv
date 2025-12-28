# FILE: detection/model/loader.py
# ------------------------------------------------------------------------------
import time

from detection.config import Config
from detection.model.base import BaseModel
from ingestion.errors.fatal import FatalError

class MockModel(BaseModel):
    def load(self):
        assert Config.MODEL_PATH
        time.sleep(0.2)

    def input_shape(self):
        return (1, 480, 640, 3)

    def predict(self, input_tensor):
        time.sleep(0.05)
        return [
            {"class_id": 0, "confidence": 0.91, "bbox": [100, 100, 50, 50]}
        ]

def load_model() -> BaseModel:
    try:
        model = MockModel()
        model.load()
        return model
    except Exception as e:
        raise FatalError("Model load failed", context={"error": str(e)})
