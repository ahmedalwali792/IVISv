# FILE: detection/model/runner.py
# ------------------------------------------------------------------------------
import signal
import time
import numpy as np
from detection.metrics.counters import metrics

from detection.errors.fatal import FatalError
# from detection.config import INFERENCE_TIMEOUT
# from detection.config import INFERENCE_TIMEOUT_SECONDS
from detection.config import INFERENCE_TIMEOUT_SECONDS

class ModelRunner:
    def __init__(self, model):
        self.model = model

    def warmup(self):
        dummy = np.zeros(self.model.input_shape(), dtype="float32")
        self.model.predict(dummy)

    def infer(self, tensor):
        def timeout_handler(signum, frame):
            raise FatalError("Inference timeout")

        if hasattr(signal, 'SIGALRM'):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(INFERENCE_TIMEOUT_SECONDS)


        start = time.time()
        try:
            return self.model.predict(tensor)
        except FatalError:
            raise
        except Exception as e:
            raise FatalError(f"Inference Engine Crash: {e}")
        finally:
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
            metrics.log_latency((time.time() - start) * 1000)
