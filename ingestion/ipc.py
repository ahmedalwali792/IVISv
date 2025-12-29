# [2025-12-29] ingestion/ipc.py
import requests
from ingestion.memory.ref import MemoryReference

class HTTPMemoryBackend:
    name = "http_ring_v1"
    
    def __init__(self, host="localhost", port=6000):
        self.url = f"http://{host}:{port}"

    def put(self, key, data):
        try:
            response = requests.put(f"{self.url}/{key}", data=data, timeout=0.5)
            if response.status_code == 200:
                meta = response.json()
                return MemoryReference(
                    location=key,
                    size=meta['size'],
                    backend_type=self.name,
                    generation=meta.get('generation', 0)
                )
            return None
        except Exception as e:
            print(f"[Backend Error] {e}")
            return None