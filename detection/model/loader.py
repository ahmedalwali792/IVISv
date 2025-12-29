# [2025-12-29] detection/model/loader.py
import time
from detection.config import Config
from detection.errors.fatal import FatalError
from detection.model.base import BaseModel

class MockModel(BaseModel):
    def load(self): time.sleep(0.2)
    def predict(self, input_tensor):
        time.sleep(0.05)
        return [{"class_id": 0, "confidence": 0.91, "bbox": [100, 100, 50, 50]}]

def load_model() -> BaseModel:
    try:
        model = MockModel()
        model.load()
        return model
    except Exception as e:
        raise FatalError(f"Model load failed: {e}")