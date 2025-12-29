# [2025-12-29] ingestion/publish/stream.py
import json
from ingestion.frame.id import FrameIdentity

class StreamPublisher:
    """
    مسؤول عن بناء العقد (Logic) وتمريره للمنتج (Transport).
    """
    def __init__(self, config, producer):
        self.stream_id = config.stream_id
        self.camera_id = config.camera_id
        self.producer = producer # Injected Dependency (BaseProducer)

    def publish(self, frame_identity, packet_timestamp, memory_ref):
        gen = getattr(memory_ref, 'generation', 0)
        
        # 1. Build Contract (Business Logic)
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
        
        # 2. Serialize
        payload = json.dumps(contract).encode('utf-8')
        
        # 3. Delegate to Blind Transport
        self.producer.publish("frames.v1", payload)
        print(f"[PUB] Frame {frame_identity.frame_id[:8]} sent")