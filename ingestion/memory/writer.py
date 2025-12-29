# [2025-12-29] ingestion/memory/writer.py
from ingestion.errors.fatal import MemoryWriteError

class Writer:
    def __init__(self, storage_backend):
        self.backend = storage_backend
    
    def write(self, frame_data, identity):
        try:
            key = identity.frame_id
            data_bytes = frame_data.tobytes()
            ref = self.backend.put(key, data_bytes)
            
            if not ref or not hasattr(ref, 'location'):
                 raise MemoryWriteError(f"Backend violation", context={"id": key})
            return ref
        except Exception as e:
            if isinstance(e, MemoryWriteError): raise e
            raise MemoryWriteError(f"Write Exception: {str(e)}", context={"id": identity.frame_id})