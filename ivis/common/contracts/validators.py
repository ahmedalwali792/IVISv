"""Frame contract validators for IVIS v1 contracts.

Provides a strict, fail-fast validator used by Detection and UI.
"""
import warnings
from typing import Any, Dict


class ContractValidationError(Exception):
    """Raised when a contract fails validation.

    Attributes:
        reason_code: short machine-friendly reason string
        message: human-friendly message
    """
    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


def validate_frame_contract_v1(contract: Dict[str, Any]) -> None:
    """Validate a v1 frame contract strictly.

    Raises ContractValidationError on any violation with a clear reason_code.
    """
    if not isinstance(contract, dict):
        raise ContractValidationError("not_a_dict", "contract must be a dict")

    # contract_version must be int 1 (temporary migration accepts "v1"/"1" strings)
    cv = contract.get("contract_version")
    if isinstance(cv, bool):
        cv = None
    warning_msg = None
    if isinstance(cv, str):
        normalized = cv.strip()
        if normalized.lower() == "v1":
            warning_msg = "contract_version 'v1' is deprecated; use int 1"
            cv = 1
        elif normalized == "1":
            warning_msg = "contract_version '1' (string) is deprecated; use int 1"
            cv = 1
    if cv != 1:
        raise ContractValidationError("contract_version_mismatch", f"unsupported contract_version={cv}")
    if warning_msg:
        warnings.warn(warning_msg, DeprecationWarning, stacklevel=2)
    if contract.get("contract_version") != 1:
        contract["contract_version"] = 1

    # Memory reference required
    mem = contract.get("memory")
    if not isinstance(mem, dict):
        raise ContractValidationError("missing_memory", "memory must be a dict")
    for field in ("backend", "key", "size", "generation"):
        if field not in mem:
            raise ContractValidationError("missing_memory_field", f"memory missing field '{field}'")
    if not isinstance(mem.get("backend"), str) or not mem.get("backend"):
        raise ContractValidationError("bad_memory_backend", "memory.backend must be a non-empty string")
    if not isinstance(mem.get("key"), str) or not mem.get("key"):
        raise ContractValidationError("bad_memory_key", "memory.key must be a non-empty string")
    if not isinstance(mem.get("size"), int) or mem.get("size") < 0:
        raise ContractValidationError("bad_memory_size", "memory.size must be a non-negative int")
    if not isinstance(mem.get("generation"), int):
        raise ContractValidationError("bad_memory_generation", "memory.generation must be an int")

    # Basic metadata
    width = contract.get("frame_width")
    height = contract.get("frame_height")
    channels = contract.get("frame_channels")
    dtype = contract.get("frame_dtype")
    color = contract.get("frame_color_space")

    for nm, val in (("frame_width", width), ("frame_height", height)):
        if not isinstance(val, int) or val <= 0:
            raise ContractValidationError("bad_dimensions", f"{nm} must be a positive int")
    # Reasonable bounds
    MIN_DIM = 16
    MAX_DIM = 10000
    if not (MIN_DIM <= width <= MAX_DIM) or not (MIN_DIM <= height <= MAX_DIM):
        raise ContractValidationError("dimension_out_of_range", f"width/height out of range: {width}x{height}")

    if not isinstance(channels, int) or channels <= 0:
        raise ContractValidationError("bad_channels", "frame_channels must be a positive int")
    if channels != 3:
        raise ContractValidationError("unsupported_channels", f"only 3 channels supported in v1; got {channels}")

    if not isinstance(dtype, str) or not dtype:
        raise ContractValidationError("bad_dtype", "frame_dtype must be a non-empty string")
    if dtype.lower() != "uint8":
        raise ContractValidationError("unsupported_dtype", f"only uint8 supported in v1; got {dtype}")

    if not isinstance(color, str) or not color:
        raise ContractValidationError("bad_color_space", "frame_color_space must be a non-empty string")
    if color.lower() != "bgr":
        raise ContractValidationError("unsupported_color_space", f"only bgr supported in v1; got {color}")

    # Verify memory size matches expected frame layout for uint8
    expected = width * height * channels
    if mem.get("size") != expected:
        raise ContractValidationError("memory_size_mismatch", f"memory.size {mem.get('size')} != expected {expected}")

    # timestamp and ids
    if "frame_id" not in contract or not isinstance(contract.get("frame_id"), str):
        raise ContractValidationError("bad_frame_id", "frame_id must be a non-empty string")
    if "stream_id" not in contract or not isinstance(contract.get("stream_id"), str):
        raise ContractValidationError("bad_stream_id", "stream_id must be a non-empty string")

    # pts/timestamp types
    if "pts" in contract and not isinstance(contract.get("pts"), (int, float)):
        raise ContractValidationError("bad_pts", "pts must be numeric")
    if "timestamp" in contract and not isinstance(contract.get("timestamp"), int):
        raise ContractValidationError("bad_timestamp", "timestamp must be int (ms)")

    # All checks passed
    return None
