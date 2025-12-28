# FILE: memory/runtime.py
# ------------------------------------------------------------------------------

from memory.config import config
from memory.backend.ring import RingBufferBackend
from memory.errors.fatal import ConfigurationError, BackendInitializationError
from memory.errors.fatal import ConfigurationError


class Runtime:
    def __init__(self):
        self.backend = None
    def initialize(self):
        if not config: raise ConfigurationError("Config Error")
        print(f"Initializing Memory Backend: {config.backend_type}")
        if config.backend_type == "ring":
            self.backend = RingBufferBackend(config.buffer_size_bytes)
        else:
            raise ConfigurationError(f"Unsupported backend")
    def get_backend(self):
        if not self.backend: raise BackendInitializationError("Not Initialized")
        return self.backend
