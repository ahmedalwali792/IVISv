# FILE: memory/api/write.py
# ------------------------------------------------------------------------------
from memory.backend.base import MemoryBackend


class WriteAPI:
    def __init__(self, backend: MemoryBackend):
        self._backend = backend
    def put(self, key: str, data: bytes):
        if not key or not data: return False
        return self._backend.put(key, data)
