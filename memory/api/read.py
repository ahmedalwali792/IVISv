# FILE: memory/api/read.py
# ------------------------------------------------------------------------------
from typing import Optional

from memory.backend.base import MemoryBackend
from memory.buffer.layout import MemoryReference

class ReadAPI:
    def __init__(self, backend: MemoryBackend):
        self._backend = backend
    def get(self, key: str) -> Optional[bytes]:
        return self._backend.get(key)
    def get_reference(self, key: str) -> Optional[MemoryReference]:
        data = self._backend.get(key)
        if data:
            return MemoryReference(location="memory", size=len(data), generation=0, backend_type=self._backend.name)
        return None
