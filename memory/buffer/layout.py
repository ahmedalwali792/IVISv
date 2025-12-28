# FILE: memory/buffer/layout.py
# ------------------------------------------------------------------------------
from dataclasses import dataclass

@dataclass(frozen=True)
class MemoryReference:
    location: str
    size: int
    generation: int
    backend_type: str

@dataclass(frozen=True)
class AllocationResult:
    offset: int
    generation: int
    success: bool
