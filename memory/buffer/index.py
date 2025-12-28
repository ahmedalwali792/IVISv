# FILE: memory/buffer/index.py
# ------------------------------------------------------------------------------
from dataclasses import dataclass
from typing import Optional

@dataclass
class IndexEntry:
    offset: int
    size: int
    generation: int

class BufferIndex:
    def __init__(self):
        self._map: dict[str, IndexEntry] = {}
    def update(self, key: str, offset: int, size: int, generation: int):
        self._map[key] = IndexEntry(offset, size, generation)
    def lookup(self, key: str) -> Optional[IndexEntry]:
        return self._map.get(key)
    def count(self) -> int:
        return len(self._map)
