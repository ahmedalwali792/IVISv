# FILE: detection/frame/decoder.py
# ------------------------------------------------------------------------------
import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np

from detection.config import Config
from detection.errors.fatal import NonFatalError

class FrameDecoder:
    """
    Blind Consumer Knowledge Base.
    Uses LOCAL constants (Config) to understand bytes.
    """
    def __init__(self):
        self._logger = logging.getLogger("detection")

    def _resolve_metadata(self, contract: Dict[str, Any]) -> Tuple[int, int, int, str, bool]:
        width = contract.get("frame_width")
        height = contract.get("frame_height")
        channels = contract.get("frame_channels")
        dtype = contract.get("frame_dtype")
        if all(v is not None for v in (width, height, channels, dtype)):
            return int(width), int(height), int(channels), str(dtype), False

        if not Config.DECODER_ALLOW_CONFIG_FALLBACK:
            raise NonFatalError("Missing frame metadata in contract (Strict Mode). Enable DECODER_ALLOW_CONFIG_FALLBACK to bypass.")

        # Rate-limiter for warnings could be added here if desired, using a static set or similar.
        self._logger.warning("Contract missing frame metadata. Falling back to Config (DECODER_ALLOW_CONFIG_FALLBACK=True).")
        return Config.FRAME_WIDTH, Config.FRAME_HEIGHT, 3, "uint8", True

    def _dtype_bytes(self, dtype: str) -> int:
        dtype_norm = dtype.lower()
        if dtype_norm == "uint8":
            return 1
        if dtype_norm == "uint16":
            return 2
        if dtype_norm == "float32":
            return 4
        raise NonFatalError(f"Unsupported frame dtype: {dtype}")

    def decode(self, data_bytes: bytes, contract: Optional[Dict[str, Any]] = None) -> np.ndarray:
        if contract is None:
            contract = {}

        width, height, channels, dtype, _ = self._resolve_metadata(contract)

        if int(channels) != 3:
            raise NonFatalError(f"Unsupported channels={channels}. Expected 3 (BGR).")

        bytes_per_pixel = self._dtype_bytes(dtype)
        expected_size = int(width) * int(height) * 3 * bytes_per_pixel

        mem = contract.get("memory") if isinstance(contract, dict) else None
        if isinstance(mem, dict) and mem.get("size") is not None:
            mem_size = mem.get("size")
            if isinstance(mem_size, str) and mem_size.isdigit():
                mem_size = int(mem_size)
            if isinstance(mem_size, int) and mem_size != expected_size:
                raise NonFatalError(
                    f"Frame size mismatch. Expected {expected_size}, got {mem_size}. "
                    f"Check contract vs shared memory."
                )

        if len(data_bytes) != expected_size:
            raise NonFatalError(
                f"Frame size mismatch. Expected {expected_size}, got {len(data_bytes)}. "
                f"Check Config or contract vs shared memory."
            )

        try:
            arr = np.frombuffer(data_bytes, dtype=dtype)
            return arr.reshape((int(height), int(width), 3))
        except Exception as e:
            raise NonFatalError(f"Failed to decode frame bytes: {e}")
