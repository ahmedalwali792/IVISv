# ------------------------------------------------------------------------------
# FILE: ingestion/config.py
# ------------------------------------------------------------------------------
import os

from ivis.common.config.base import ConfigLoadError, EnvLoader, redact_config
from ingestion.errors.fatal import ConfigError


class Config:
    def __init__(self):
        schema = {
            "RTSP_URL": {"type": "str", "required": True},
            "STREAM_ID": {"type": "str", "required": True},
            "CAMERA_ID": {"type": "str", "required": True},
            "TARGET_FPS": {"type": "int", "required": True},
            "FRAME_WIDTH": {"type": "int", "required": True},
            "FRAME_HEIGHT": {"type": "int", "required": True},
            "MEMORY_BACKEND": {"type": "str", "required": True},
            "BUS_TRANSPORT": {"type": "str", "default": "redis"},
            "ZMQ_PUB_ENDPOINT": {"type": "str", "default": "tcp://localhost:5555"},
            "REDIS_URL": {"type": "str", "default": "redis://localhost:6379/0"},
            "REDIS_STREAM": {"type": "str", "default": "ivis:frames"},
            "REDIS_MODE": {"type": "str", "default": "streams"},
            "REDIS_CHANNEL": {"type": "str", "default": "ivis:frames"},
            "REDIS_RESULTS_CHANNEL": {"type": "str", "default": "ivis:results"},
            # SOURCE_COLOR is the color of the raw source (camera/file). Ingestion
            # will convert from SOURCE_COLOR -> FRAME_COLOR_SPACE for downstream.
            "SOURCE_COLOR": {"type": "str", "default": None},
            "FRAME_COLOR": {"type": "str", "default": "bgr"},
            "SHM_NAME": {"type": "str", "default": "ivis_shm_data"},
            "SHM_META_NAME": {"type": "str", "default": "ivis_shm_meta"},
            "SHM_BUFFER_BYTES": {"type": "int", "default": 50000000},
            "SELECTOR_MODE": {"type": "str", "default": "clock"},
            "ADAPTIVE_FPS": {"type": "bool", "default": False},
            "ADAPTIVE_MIN_FPS": {"type": "float", "default": 5},
            "ADAPTIVE_MAX_FPS": {"type": "float", "default": None},
            "ADAPTIVE_SAFETY": {"type": "float", "default": 1.3},
            "VIDEO_LOOP": {"type": "bool", "default": False},
            "RTSP_MAX_RETRIES": {"type": "int", "default": 0},
            "RTSP_RETRY_BACKOFF_SEC": {"type": "float", "default": 1.0},
        }
        loader = EnvLoader()
        try:
            values = loader.load(schema)
        except ConfigLoadError as exc:
            raise ConfigError("Invalid config", context={"error": str(exc)}) from exc
        self._values = values

        self.rtsp_url = values["RTSP_URL"]
        self.stream_id = values["STREAM_ID"]
        self.camera_id = values["CAMERA_ID"]
        self.target_fps = values["TARGET_FPS"]

        self.frame_width = values["FRAME_WIDTH"]
        self.frame_height = values["FRAME_HEIGHT"]

        self.memory_backend = values["MEMORY_BACKEND"]
        self.bus_transport = values["BUS_TRANSPORT"]
        self.zmq_pub_endpoint = values["ZMQ_PUB_ENDPOINT"]
        self.redis_url = values["REDIS_URL"]
        self.redis_stream = values["REDIS_STREAM"]
        self.redis_mode = values["REDIS_MODE"]
        self.redis_channel = values["REDIS_CHANNEL"]
        self.redis_results_channel = values["REDIS_RESULTS_CHANNEL"]
        # Prefer SOURCE_COLOR (new); fall back to FRAME_COLOR legacy variable.
        src_col = values.get("SOURCE_COLOR")
        if src_col:
            src = src_col.lower()
        else:
            # migration from legacy FRAME_COLOR
            src = values["FRAME_COLOR"].lower() if values.get("FRAME_COLOR") else "bgr"
            if os.getenv("FRAME_COLOR"):
                import warnings

                warnings.warn(
                    "Environment variable FRAME_COLOR is deprecated; mapped to SOURCE_COLOR for ingestion.",
                    DeprecationWarning,
                )

        if src not in ("bgr", "rgb"):
            src = "bgr"
        self.frame_color = src
        self.shm_name = values["SHM_NAME"]
        self.shm_meta_name = values["SHM_META_NAME"]
        self.shm_buffer_bytes = values["SHM_BUFFER_BYTES"]
        self.selector_mode = values["SELECTOR_MODE"].lower()
        self.adaptive_fps = values["ADAPTIVE_FPS"]
        self.adaptive_min_fps = values["ADAPTIVE_MIN_FPS"]
        self.adaptive_max_fps = values["ADAPTIVE_MAX_FPS"] or float(self.target_fps)
        self.adaptive_safety = values["ADAPTIVE_SAFETY"]
        self.video_loop = values["VIDEO_LOOP"]
        self.rtsp_max_retries = values["RTSP_MAX_RETRIES"]
        self.rtsp_retry_backoff_sec = values["RTSP_RETRY_BACKOFF_SEC"]

        self._validate()

    def _validate(self):
        if self.target_fps <= 0:
            raise ConfigError("Invalid TARGET_FPS", context={"value": self.target_fps})
        if self.frame_width <= 0 or self.frame_height <= 0:
            raise ConfigError("Invalid resolution", context={"w": self.frame_width, "h": self.frame_height})
        if self.memory_backend not in ("shm",):
            raise ConfigError("Unsupported MEMORY_BACKEND", context={"value": self.memory_backend})
        if self.shm_buffer_bytes <= 0:
            raise ConfigError("Invalid SHM_BUFFER_BYTES", context={"value": self.shm_buffer_bytes})
        if self.selector_mode not in ("clock", "pts"):
            raise ConfigError("Invalid SELECTOR_MODE", context={"value": self.selector_mode})
        if self.rtsp_max_retries < 0:
            raise ConfigError("Invalid RTSP_MAX_RETRIES", context={"value": self.rtsp_max_retries})
        if self.rtsp_retry_backoff_sec < 0:
            raise ConfigError("Invalid RTSP_RETRY_BACKOFF_SEC", context={"value": self.rtsp_retry_backoff_sec})

    @property
    def resolution(self):
        return (self.frame_width, self.frame_height)

    def summary(self) -> dict:
        return redact_config(self._values)
