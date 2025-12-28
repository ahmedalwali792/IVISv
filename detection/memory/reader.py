# FILE: detection/memory/reader.py
# ------------------------------------------------------------------------------
import requests

from detection.errors.fatal import NonFatalError

class MemoryReader:
    """
    Stage 3: Reads Raw Bytes Only.
    No decoding, no reshaping here. Just bytes.
    """
    def __init__(self, host="localhost", port=6000):
        self.url = f"http://{host}:{port}"

    def read(self, memory_ref: dict) -> bytes:
        key = memory_ref.get("key")
        
        if not key:
            raise NonFatalError("Invalid memory reference: missing key")

        try:
            resp = requests.get(f"{self.url}/{key}", timeout=0.5)
            
            if resp.status_code == 200:
                data_bytes = resp.content
                if len(data_bytes) == 0:
                     raise NonFatalError("Empty data received from memory")
                
                return data_bytes

            elif resp.status_code == 404:
                raise NonFatalError("Memory Miss (Frame evicted or invalid)")
            else:
                raise NonFatalError(f"Memory read error: HTTP {resp.status_code}")
                
        except requests.exceptions.RequestException as e:
            raise NonFatalError(f"Memory connection failed: {str(e)}")
        except Exception as e:
            if isinstance(e, NonFatalError): raise e
            raise NonFatalError(f"Memory processing failed: {str(e)}")
