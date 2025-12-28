# FILE: memory/config.py
# ------------------------------------------------------------------------------
import os

from memory.errors.fatal import ConfigurationError

class Config:
    def __init__(self):
        self.backend_type = os.getenv("MEMORY_BACKEND")
        self.buffer_size_bytes = self._get_int("BUFFER_SIZE_BYTES")
        self.max_frame_size_bytes = self._get_int("MAX_FRAME_SIZE_BYTES")
        self._validate()

    def _get_int(self, key: str) -> int:
        val = os.getenv(key)
        if val is None:
            raise ConfigurationError(f"Missing mandatory config: {key}")
        try:
            return int(val)
        except ValueError:
            raise ConfigurationError(f"Config {key} must be an integer")

    def _validate(self):
        required_min_size = self.max_frame_size_bytes * 2
        if self.buffer_size_bytes < required_min_size:
            raise ConfigurationError(f"Buffer size too small.")
        if self.backend_type != "ring":
             raise ConfigurationError(f"Fatal: Only 'ring' backend is supported.")
try:
    config = Config()
except ConfigurationError:
    if os.getenv("MEMORY_STRICT_MODE", "1") == "1": raise
    config = None
