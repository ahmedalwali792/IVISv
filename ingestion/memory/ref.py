# FILE: ingestion/memory/ref.py
# ------------------------------------------------------------------------------
class MemoryReference:
    def __init__(self, location, size, backend_type, generation=0):
        self.location = location
        self.size = size
        self.backend_type = backend_type
        self.generation = generation

    def __repr__(self):
        return f"Ref(loc={self.location}, sz={self.size}, gen={self.generation}, type={self.backend_type})"
