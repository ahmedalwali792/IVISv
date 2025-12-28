# ------------------------------------------------------------------------------
# FILE: ingestion/errors/fatal.py
# ------------------------------------------------------------------------------
class FatalError(Exception):
    def __init__(self, message, context=None):
        self.message = message
        self.context = context or {}
        super().__init__(self.message)

class ConfigError(FatalError):
    pass

class MemoryWriteError(FatalError):
    pass
