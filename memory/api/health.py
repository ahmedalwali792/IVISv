# FILE: memory/api/health.py
# ------------------------------------------------------------------------------
from memory.backend.base import MemoryBackend


class HealthAPI:
    def __init__(self, backend: MemoryBackend):
        self._backend = backend
    def is_alive(self) -> bool:
        return True 
    def stats(self) -> dict:
        return self._backend.stats()
