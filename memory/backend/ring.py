# FILE: memory/backend/ring.py
# ------------------------------------------------------------------------------
from typing import Union

from typing import Optional

from memory.backend.base import MemoryBackend
from memory.buffer.allocator import RingAllocator
from memory.buffer.index import BufferIndex
from memory.buffer.layout import MemoryReference
from memory.errors.fatal import BackendInitializationError
from memory.metrics.counters import Metrics

class RingBufferBackend(MemoryBackend):
    name = "ring_v1"
    def __init__(self, capacity_bytes: int):
        self.capacity = capacity_bytes
        try:
            self._buffer = bytearray(capacity_bytes)
        except MemoryError:
            raise BackendInitializationError("Failed to allocate raw memory buffer")
        self._allocator = RingAllocator(capacity_bytes)
        self._index = BufferIndex()
        self._metrics = Metrics.get()

    def put(self, key: str, data: bytes) -> Union[MemoryReference, bool]:
        data_len = len(data)
        alloc = self._allocator.allocate(data_len)
        if not alloc.success:
            self._metrics.inc_write_fail()
            return False

        try:
            end_pos = alloc.offset + data_len
            self._buffer[alloc.offset : end_pos] = data
        except Exception:
            self._metrics.inc_write_fail()
            return False

        self._index.update(key, alloc.offset, data_len, alloc.generation)
        self._metrics.inc_write_ok()
        
        return MemoryReference(location=key, size=data_len, generation=alloc.generation, backend_type=self.name)

    def get(self, key: str) -> Optional[bytes]:
        entry = self._index.lookup(key)
        if not entry:
            self._metrics.inc_read_miss()
            return None
        current_gen = self._allocator.current_generation()
        if entry.generation != current_gen:
            self._metrics.inc_read_miss()
            self._metrics.evictions += 1
            return None
        end_pos = entry.offset + entry.size
        data_copy = bytes(self._buffer[entry.offset : end_pos])
        self._metrics.inc_read_ok()
        return data_copy

    def stats(self) -> dict:
        base_stats = self._metrics.snapshot()
        base_stats["index_count"] = self._index.count()
        base_stats["backend"] = self.name
        return base_stats
