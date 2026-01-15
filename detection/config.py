# FILE: detection/config.py
# ------------------------------------------------------------------------------
from ivis.common.config.base import ConfigLoadError, EnvLoader, redact_config
from detection.errors.fatal import FatalError


_SCHEMA = {
    "MODEL_NAME": {"type": "str", "required": True},
    "MODEL_VERSION": {"type": "str", "required": True},
    "MODEL_HASH": {"type": "str", "required": True},
    "MODEL_PATH": {"type": "str", "required": True},
    "INFERENCE_TIMEOUT": {"type": "int", "default": 5},
    "MODEL_DEVICE": {"type": "str", "default": "auto"},
    "MODEL_HALF": {"type": "bool", "default": False},
    "MODEL_IMG_SIZE": {"type": "int", "default": 640},
    "MODEL_CONF": {"type": "float", "default": 0.25},
    "MODEL_IOU": {"type": "float", "default": 0.5},
    "TRACKER_MAX_AGE": {"type": "int", "default": 8},
    "TRACKER_INIT_FRAMES": {"type": "int", "default": 3},
    "TRACKER_NN_BUDGET": {"type": "int", "default": 100},
    "TRACKER_MAX_IOU": {"type": "float", "default": 0.7},
    "REID_MODEL_NAME": {"type": "str", "default": "osnet_x0_25"},
    "REID_MODEL_PATH": {"type": "str", "default": None},
    "REID_ALLOW_FALLBACK": {"type": "bool", "default": False},
    "BUS_TRANSPORT": {"type": "str", "default": "zmq"},
    "ZMQ_PUB_ENDPOINT": {"type": "str", "default": "tcp://localhost:5555"},
    "ZMQ_SUB_ENDPOINT": {"type": "str", "default": "tcp://localhost:5555"},
    "ZMQ_RESULTS_PUB_ENDPOINT": {"type": "str", "default": "tcp://localhost:5557"},
    "POSTGRES_DSN": {"type": "str", "default": None},
    "FRAME_WIDTH": {"type": "int", "default": 640},
    "FRAME_HEIGHT": {"type": "int", "default": 480},
    "FRAME_COLOR": {"type": "str", "default": "bgr"},
    "MEMORY_BACKEND": {"type": "str", "default": "shm"},
    "SHM_NAME": {"type": "str", "default": "ivis_shm_data"},
    "SHM_META_NAME": {"type": "str", "default": "ivis_shm_meta"},
    "SHM_BUFFER_BYTES": {"type": "int", "default": 50000000},
    "SHM_CACHE_SECONDS": {"type": "float", "default": 0},
    "SHM_CACHE_FPS": {"type": "float", "default": 0},
    "MAX_FRAME_AGE_MS": {"type": "int", "default": 1000},
    "DEBUG": {"type": "bool", "default": False},
}


def _load_config() -> dict:
    loader = EnvLoader()
    try:
        values = loader.load(_SCHEMA)
    except ConfigLoadError as exc:
        raise FatalError("Invalid config", context={"error": str(exc)}) from exc
    if values["INFERENCE_TIMEOUT"] <= 0:
        raise FatalError("INFERENCE_TIMEOUT must be > 0")
    return values


class Config:
    _VALUES = _load_config()

    MODEL_NAME = _VALUES["MODEL_NAME"]
    MODEL_VERSION = _VALUES["MODEL_VERSION"]
    MODEL_HASH = _VALUES["MODEL_HASH"]
    MODEL_PATH = _VALUES["MODEL_PATH"]

    INFERENCE_TIMEOUT_SECONDS = _VALUES["INFERENCE_TIMEOUT"]

    # Device/runtime tuning
    MODEL_DEVICE = _VALUES["MODEL_DEVICE"]
    MODEL_HALF = _VALUES["MODEL_HALF"]
    MODEL_IMG_SIZE = _VALUES["MODEL_IMG_SIZE"]
    MODEL_CONF = _VALUES["MODEL_CONF"]
    MODEL_IOU = _VALUES["MODEL_IOU"]

    # Tracking / ReID
    TRACKER_MAX_AGE = _VALUES["TRACKER_MAX_AGE"]
    TRACKER_INIT_FRAMES = _VALUES["TRACKER_INIT_FRAMES"]
    TRACKER_NN_BUDGET = _VALUES["TRACKER_NN_BUDGET"]
    TRACKER_MAX_IOU = _VALUES["TRACKER_MAX_IOU"]
    REID_MODEL_NAME = _VALUES["REID_MODEL_NAME"]
    REID_MODEL_PATH = _VALUES["REID_MODEL_PATH"]
    REID_ALLOW_FALLBACK = _VALUES["REID_ALLOW_FALLBACK"]

    # Bus transport: zmq | tcp
    BUS_TRANSPORT = _VALUES["BUS_TRANSPORT"]
    ZMQ_PUB_ENDPOINT = _VALUES["ZMQ_PUB_ENDPOINT"]
    ZMQ_SUB_ENDPOINT = _VALUES["ZMQ_SUB_ENDPOINT"]
    ZMQ_RESULTS_PUB_ENDPOINT = _VALUES["ZMQ_RESULTS_PUB_ENDPOINT"]

    # Persistence
    POSTGRES_DSN = _VALUES["POSTGRES_DSN"]

    # Blind Consumer Config (Decoupled from Orchestrator)
    FRAME_WIDTH = _VALUES["FRAME_WIDTH"]
    FRAME_HEIGHT = _VALUES["FRAME_HEIGHT"]
    FRAME_COLOR = _VALUES["FRAME_COLOR"].lower()

    MEMORY_BACKEND = _VALUES["MEMORY_BACKEND"]
    SHM_NAME = _VALUES["SHM_NAME"]
    SHM_META_NAME = _VALUES["SHM_META_NAME"]
    SHM_BUFFER_BYTES = _VALUES["SHM_BUFFER_BYTES"]
    SHM_CACHE_SECONDS = _VALUES["SHM_CACHE_SECONDS"]
    SHM_CACHE_FPS = _VALUES["SHM_CACHE_FPS"]
    MAX_FRAME_AGE_MS = _VALUES["MAX_FRAME_AGE_MS"]

    DEBUG = _VALUES["DEBUG"]

    @classmethod
    def summary(cls) -> dict:
        return redact_config(cls._VALUES)
