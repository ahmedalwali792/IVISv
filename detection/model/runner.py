# [2025-12-29] detection/model/runner.py
import time
from detection.config import Config
from detection.errors.fatal import FatalError
from detection.metrics.counters import metrics

class ModelRunner:
    def __init__(self, model):
        self.model = model
    def warmup(self):
        pass
    def infer(self, tensor):
        start = time.time()
        try:
            return self.model.predict(tensor)
        finally:
            metrics.log_latency((time.time() - start) * 1000)