# FILE: ingestion/frame/id.py
# ------------------------------------------------------------------------------
import hashlib

class FrameIdentity:
    def __init__(self, stream_id, pts, fingerprint):
        self.stream_id = stream_id
        self.pts = pts
        self.fingerprint = fingerprint
        raw_key = f"{stream_id}_{pts:.6f}_{fingerprint}"
        self.frame_id = hashlib.md5(raw_key.encode()).hexdigest()

    def to_dict(self):
        return {
            "id": self.frame_id,
            "stream": self.stream_id,
            "pts": self.pts,
            "anchor": self.fingerprint
        }
