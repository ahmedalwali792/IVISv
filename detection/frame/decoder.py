# FILE: detection/frame/decoder.py
# ------------------------------------------------------------------------------
import numpy as np

from detection.config import Config
from detection.errors.fatal import NonFatalError

class FrameDecoder:
    """
    Blind Consumer Knowledge Base.
    Uses LOCAL constants (Config) to understand bytes.
    """
    def __init__(self):
        self.shape = (Config.FRAME_HEIGHT, Config.FRAME_WIDTH, 3)
        self.dtype = "uint8"
        self.expected_size = np.prod(self.shape)

    def decode(self, data_bytes: bytes) -> np.ndarray:
        if len(data_bytes) != self.expected_size:
            raise NonFatalError(
                f"Frame size mismatch. Expected {self.expected_size}, got {len(data_bytes)}. "
                f"Check Config vs Ingestion."
            )
        
        try:
            arr = np.frombuffer(data_bytes, dtype=self.dtype)
            return arr.reshape(self.shape)
        except Exception as e:
            raise NonFatalError(f"Failed to decode frame bytes: {e}")
