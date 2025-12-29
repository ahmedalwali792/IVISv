# [2025-12-29] detection/memory/reader.py
import requests
from detection.errors.fatal import NonFatalError

class MemoryReader:
    def __init__(self, host="localhost", port=6000):
        self.url = f"http://{host}:{port}"

    def read(self, memory_ref: dict) -> bytes:
        key = memory_ref.get("key")
        if not key: raise NonFatalError("Invalid memory reference")

        try:
            resp = requests.get(f"{self.url}/{key}", timeout=0.5)
            if resp.status_code == 200:
                return resp.content
            elif resp.status_code == 404:
                raise NonFatalError("Memory Miss")
            else:
                raise NonFatalError(f"HTTP {resp.status_code}")
        except Exception as e:
            if isinstance(e, NonFatalError): raise e
            raise NonFatalError(f"Memory Fail: {str(e)}")