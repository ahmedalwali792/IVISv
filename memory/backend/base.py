# FILE: memory/backend/base.py
# ------------------------------------------------------------------------------
from abc import ABC, abstractmethod
from typing import Optional, Any

class MemoryBackend(ABC):
    name: str = "base"
    @abstractmethod
    def put(self, key: str, data: bytes) -> Any: pass
    @abstractmethod
    def get(self, key: str) -> Optional[bytes]: pass
    @abstractmethod
    def stats(self) -> dict: pass
