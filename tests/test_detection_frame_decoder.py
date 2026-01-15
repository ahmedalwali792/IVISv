import os

# Ensure required detection config vars exist BEFORE importing FrameDecoder (Config loads at import time).
os.environ.setdefault("MODEL_NAME", "stub")
os.environ.setdefault("MODEL_VERSION", "0")
os.environ.setdefault("MODEL_HASH", "stub")
os.environ.setdefault("MODEL_PATH", "stub.pt")

from detection.frame.decoder import FrameDecoder  # noqa: E402
import numpy as np


def test_decoder_uses_contract_metadata_when_present():
    dec = FrameDecoder()
    w, h, c = 4, 3, 3
    data = bytes(range(w * h * c))
    contract = {
        "frame_width": w,
        "frame_height": h,
        "frame_channels": c,
        "frame_dtype": "uint8",
        "memory": {"size": len(data)},
    }
    arr = dec.decode(data, contract)
    assert arr.shape == (h, w, c)


def test_decoder_accepts_memory_size_as_string():
    dec = FrameDecoder()
    w, h, c = 2, 2, 3
    data = bytes(range(w * h * c))
    contract = {
        "frame_width": w,
        "frame_height": h,
        "frame_channels": c,
        "frame_dtype": "uint8",
        "memory": {"size": str(len(data))},
    }
    arr = dec.decode(data, contract)
    assert arr.shape == (h, w, c)


def test_decoder_rejects_wrong_size():
    dec = FrameDecoder()
    w, h, c = 2, 2, 3
    data = bytes(range((w * h * c) - 1))  # wrong
    contract = {
        "frame_width": w,
        "frame_height": h,
        "frame_channels": c,
        "frame_dtype": "uint8",
        "memory": {"size": w * h * c},
    }
    try:
        dec.decode(data, contract)
        assert False, "Expected size mismatch error"
    except Exception:
        assert True
