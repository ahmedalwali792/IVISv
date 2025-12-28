# FILE: memory/buffer/allocator.py
# ------------------------------------------------------------------------------
from memory.buffer.layout import AllocationResult


class RingAllocator:
    def __init__(self, buffer_capacity: int):
        self.capacity = buffer_capacity
        self.write_offset = 0
        self.wrap_count = 0

    def allocate(self, size: int) -> AllocationResult:
        if size > self.capacity:
            return AllocationResult(0, 0, False)
        if self.write_offset + size > self.capacity:
            self.write_offset = 0
            self.wrap_count += 1
        
        allocated_offset = self.write_offset
        allocated_generation = self.wrap_count
        self.write_offset += size
        return AllocationResult(allocated_offset, allocated_generation, True)

    def current_generation(self) -> int:
        return self.wrap_count
