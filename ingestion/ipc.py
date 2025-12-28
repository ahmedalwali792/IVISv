# FILE: ingestion/ipc.py
# ------------------------------------------------------------------------------
import requests
import socket
import json

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

class SocketPublisher:
    """
    Stage 3: Clean Protocol (No shape/dtype in contract).
    """
    def __init__(self, config, host="localhost", port=5555):
        self.stream_id = config.stream_id
        self.camera_id = config.camera_id
        self.address = (host, port)
        self.sock = None
        self._connect()

    def _connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(self.address)
        except:
            self.sock = None

    def publish(self, frame_identity, packet_timestamp, memory_ref):
        gen = getattr(memory_ref, 'generation', 0) 
        
        contract = {
            "frame_id": frame_identity.frame_id,
            "stream_id": self.stream_id,
            "camera_id": self.camera_id,
            "pts": frame_identity.pts,
            "timestamp": packet_timestamp,
            "memory": {
                "backend": "ring_v1",
                "key": memory_ref.location,
                "size": memory_ref.size,
                "generation": gen
            }
        }
        
        payload = json.dumps(contract) + "\n"
        
        if self.sock:
            try:
                self.sock.sendall(payload.encode())
            except:
                print("[PUB] Transport lost. Dropping msg.")
                self.sock.close()
                self._connect()
        else:
             self._connect()
