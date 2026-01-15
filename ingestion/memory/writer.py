# FILE: ingestion/memory/writer.py
# ------------------------------------------------------------------------------
from ingestion.errors.fatal import MemoryWriteError
from ingestion.memory.ref import MemoryReference


class Writer:
    def __init__(self, storage_backend):
        self.backend = storage_backend
    
    def write(self, frame_data, identity):
        try:
            key = identity.frame_id
            if hasattr(self.backend, "put_frame"):
                ref = self.backend.put_frame(key, frame_data)
            else:
                data_bytes = frame_data.tobytes()
                ref = self.backend.put(key, data_bytes)
            
            if not isinstance(ref, MemoryReference):
                 raise MemoryWriteError(
                     f"Backend violation: Expected MemoryReference, got {type(ref)}", 
                     context={"id": key}
                 )
            return ref
        except Exception as e:
            if isinstance(e, MemoryWriteError): raise e
            raise MemoryWriteError(f"Write Exception: {str(e)}", context={"id": identity.frame_id})
