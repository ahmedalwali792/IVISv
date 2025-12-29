# [2025-12-29] detection/preprocess/validate.py
from detection.errors.fatal import NonFatalError

def validate_frame(contract: dict):
    required_root = ["frame_id", "stream_id", "camera_id", "pts", "timestamp", "memory"]
    for field in required_root:
        if field not in contract: raise NonFatalError(f"Missing {field}")
    
    if "memory" not in contract: raise NonFatalError("Missing memory")
    if "key" not in contract["memory"]: raise NonFatalError("Missing memory key")