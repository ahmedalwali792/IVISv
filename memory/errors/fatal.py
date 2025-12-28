# FILE: memory/errors/fatal.py
# ------------------------------------------------------------------------------
class MemoryFatalError(Exception):
    pass
class ConfigurationError(MemoryFatalError):
    pass
class BackendInitializationError(MemoryFatalError):
    pass
