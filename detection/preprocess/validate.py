# FILE: detection/preprocess/validate.py
# ------------------------------------------------------------------------------
from detection.errors.fatal import NonFatalError


def validate_frame(contract: dict):
    """
    تطبيق قواعد Frame Contract v1 (Cleaned).
    """
    required_root = ["frame_id", "stream_id", "camera_id", "pts", "timestamp", "memory"]
    for field in required_root:
        if field not in contract:
            raise NonFatalError(f"Contract Violation: Missing root field '{field}'")

    mem = contract["memory"]
    if not isinstance(mem, dict):
         raise NonFatalError("Contract Violation: 'memory' must be a dict")
         
    required_mem = ["backend", "key", "size", "generation"]
    for field in required_mem:
        if field not in mem:
            raise NonFatalError(f"Contract Violation: Missing memory field '{field}'")

    if not isinstance(mem["generation"], int):
        raise NonFatalError("Contract Violation: generation must be int")
    
    if not isinstance(contract["timestamp"], int):
        raise NonFatalError("Contract Violation: timestamp must be int (ms)")
