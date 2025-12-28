# FILE: detection/config.py
# ------------------------------------------------------------------------------
import os

INFERENCE_TIMEOUT_SECONDS = int(
    os.getenv("INFERENCE_TIMEOUT", "2")
)


from detection.errors.fatal import FatalError

def _require(key: str) -> str:
    val = os.getenv(key)
    if val is None:
        raise FatalError("Missing required environment variable", context={"key": key})
    return val

class Config:
    MODEL_NAME = _require("MODEL_NAME")
    MODEL_VERSION = _require("MODEL_VERSION")
    MODEL_HASH = _require("MODEL_HASH")
    MODEL_PATH = _require("MODEL_PATH")

    INFERENCE_TIMEOUT_SECONDS = int(_require("INFERENCE_TIMEOUT"))
    if INFERENCE_TIMEOUT_SECONDS <= 0:
        raise FatalError("INFERENCE_TIMEOUT must be > 0")

    # Reserved for Stage 4 (Routing / Multi-topic)
    # Unused in Frozen v1
    # INPUT_TOPIC = _require("INPUT_TOPIC")
    # OUTPUT_TOPIC = _require("OUTPUT_TOPIC")
    
    # 🆕 Blind Consumer Config (Decoupled from Orchestrator)
    FRAME_WIDTH = 640
    FRAME_HEIGHT = 480

    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
