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
            "BUS_TRANSPORT": {"type": "str", "default": "zmq"},
            "ZMQ_PUB_ENDPOINT": {"type": "str", "default": "tcp://localhost:5555"},
            "ZMQ_RESULTS_SUB_ENDPOINT": {"type": "str", "default": "tcp://localhost:5557"},
            # SOURCE_COLOR is the color of the raw source (camera/file). Ingestion
            # will convert from SOURCE_COLOR -> FRAME_COLOR_SPACE for downstream.
            "SOURCE_COLOR": {"type": "str", "default": None},
            "FRAME_COLOR": {"type": "str", "default": "bgr"},
            "SHM_NAME": {"type": "str", "default": "ivis_shm_data"},
            "SHM_META_NAME": {"type": "str", "default": "ivis_shm_meta"},
            "SHM_BUFFER_BYTES": {"type": "int", "default": 50000000},
            "SHM_CACHE_SECONDS": {"type": "float", "default": 30.0},
            "SELECTOR_MODE": {"type": "str", "default": "clock"},
            "ADAPTIVE_FPS": {"type": "bool", "default": False},
            "ADAPTIVE_MIN_FPS": {"type": "float", "default": 5},
            "ADAPTIVE_MAX_FPS": {"type": "float", "default": None},
            "ADAPTIVE_SAFETY": {"type": "float", "default": 1.3},
            "VIDEO_LOOP": {"type": "bool", "default": False},
            "RTSP_MAX_RETRIES": {"type": "int", "default": 0},
            "RTSP_RETRY_BACKOFF_SEC": {"type": "float", "default": 1.0},
            "RTSP_RECONNECT_MIN_SEC": {"type": "float", "default": 0.5},
            "RTSP_RECONNECT_MAX_SEC": {"type": "float", "default": 30.0},
            "RTSP_RECONNECT_FACTOR": {"type": "float", "default": 2.0},
            "RTSP_RECONNECT_JITTER": {"type": "float", "default": 0.2},
            "RTSP_FROZEN_TIMEOUT_SEC": {"type": "float", "default": 30.0},
            "RTSP_FROZEN_HASH_COUNT": {"type": "int", "default": 300},
            "RTSP_FROZEN_PTS_COUNT": {"type": "int", "default": 30},
            "RTSP_FROZEN_TIMESTAMP_COUNT": {"type": "int", "default": 30},
            "HEALTH_INTERVAL_SEC": {"type": "float", "default": 5.0},
            "ADAPTIVE_LAG_THRESHOLD": {"type": "int", "default": 2000},
            "ADAPTIVE_LAG_HYSTERESIS": {"type": "float", "default": 0.2},
            "ROI_BOXES": {"type": "str", "default": None},
            "ROI_POLYGONS": {"type": "str", "default": None},
            "RECORD_BUFFER_SECONDS": {"type": "float", "default": 0},
            "RECORD_JPEG_QUALITY": {"type": "int", "default": 85},
            "RECORD_BUFFER_MAX_FRAMES": {"type": "int", "default": None},
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
        self.zmq_results_sub_endpoint = values["ZMQ_RESULTS_SUB_ENDPOINT"]
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
        self.shm_cache_seconds = values["SHM_CACHE_SECONDS"]
        if os.getenv("SHM_BUFFER_BYTES") is None and self.shm_cache_seconds > 0:
            slot_size = self.frame_width * self.frame_height * 3
            slots = max(1, int(self.target_fps * self.shm_cache_seconds))
            self.shm_buffer_bytes = slot_size * slots
        self.selector_mode = values["SELECTOR_MODE"].lower()
        self.adaptive_fps = values["ADAPTIVE_FPS"]
        self.adaptive_min_fps = values["ADAPTIVE_MIN_FPS"]
        self.adaptive_max_fps = values["ADAPTIVE_MAX_FPS"] or float(self.target_fps)
        self.adaptive_safety = values["ADAPTIVE_SAFETY"]
        self.video_loop = values["VIDEO_LOOP"]
        self.rtsp_max_retries = values["RTSP_MAX_RETRIES"]
        self.rtsp_retry_backoff_sec = values["RTSP_RETRY_BACKOFF_SEC"]
        if os.getenv("RTSP_RECONNECT_MIN_SEC") is None:
            self.rtsp_reconnect_min_sec = self.rtsp_retry_backoff_sec
        else:
            self.rtsp_reconnect_min_sec = values["RTSP_RECONNECT_MIN_SEC"]
        if os.getenv("RTSP_RECONNECT_MAX_SEC") is None:
            self.rtsp_reconnect_max_sec = max(self.rtsp_reconnect_min_sec, self.rtsp_retry_backoff_sec * 10.0)
        else:
            self.rtsp_reconnect_max_sec = values["RTSP_RECONNECT_MAX_SEC"]
        self.rtsp_reconnect_factor = values["RTSP_RECONNECT_FACTOR"]
        self.rtsp_reconnect_jitter = values["RTSP_RECONNECT_JITTER"]
        self.rtsp_frozen_timeout_sec = values["RTSP_FROZEN_TIMEOUT_SEC"]
        self.rtsp_frozen_hash_count = values["RTSP_FROZEN_HASH_COUNT"]
        self.rtsp_frozen_pts_count = values["RTSP_FROZEN_PTS_COUNT"]
        self.rtsp_frozen_timestamp_count = values["RTSP_FROZEN_TIMESTAMP_COUNT"]
        self.health_interval_sec = values["HEALTH_INTERVAL_SEC"]
        self.adaptive_lag_threshold = values["ADAPTIVE_LAG_THRESHOLD"]
        self.adaptive_lag_hysteresis = values["ADAPTIVE_LAG_HYSTERESIS"]
        self.roi_boxes = values["ROI_BOXES"]
        self.roi_polygons = values["ROI_POLYGONS"]
        self.record_buffer_seconds = values["RECORD_BUFFER_SECONDS"]
        self.record_jpeg_quality = values["RECORD_JPEG_QUALITY"]
        self.record_buffer_max_frames = values["RECORD_BUFFER_MAX_FRAMES"]

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
        if self.shm_cache_seconds < 0:
            raise ConfigError("Invalid SHM_CACHE_SECONDS", context={"value": self.shm_cache_seconds})
        if self.rtsp_max_retries < 0:
            raise ConfigError("Invalid RTSP_MAX_RETRIES", context={"value": self.rtsp_max_retries})
        if self.rtsp_retry_backoff_sec < 0:
            raise ConfigError("Invalid RTSP_RETRY_BACKOFF_SEC", context={"value": self.rtsp_retry_backoff_sec})
        if self.rtsp_reconnect_min_sec < 0 or self.rtsp_reconnect_max_sec < 0:
            raise ConfigError("Invalid RTSP_RECONNECT_MIN_SEC/RTSP_RECONNECT_MAX_SEC")
        if self.rtsp_reconnect_factor < 1.0:
            raise ConfigError("Invalid RTSP_RECONNECT_FACTOR", context={"value": self.rtsp_reconnect_factor})
        if self.rtsp_reconnect_jitter < 0:
            raise ConfigError("Invalid RTSP_RECONNECT_JITTER", context={"value": self.rtsp_reconnect_jitter})
        if self.rtsp_frozen_timeout_sec < 0:
            raise ConfigError("Invalid RTSP_FROZEN_TIMEOUT_SEC", context={"value": self.rtsp_frozen_timeout_sec})
        if self.health_interval_sec <= 0:
            raise ConfigError("Invalid HEALTH_INTERVAL_SEC", context={"value": self.health_interval_sec})
        if self.adaptive_lag_threshold < 0:
            raise ConfigError("Invalid ADAPTIVE_LAG_THRESHOLD", context={"value": self.adaptive_lag_threshold})
        if self.adaptive_lag_hysteresis < 0:
            raise ConfigError("Invalid ADAPTIVE_LAG_HYSTERESIS", context={"value": self.adaptive_lag_hysteresis})
        if self.record_buffer_seconds < 0:
            raise ConfigError("Invalid RECORD_BUFFER_SECONDS", context={"value": self.record_buffer_seconds})
        if self.record_jpeg_quality <= 0 or self.record_jpeg_quality > 100:
            raise ConfigError("Invalid RECORD_JPEG_QUALITY", context={"value": self.record_jpeg_quality})

    @property
    def resolution(self):
        return (self.frame_width, self.frame_height)

    def summary(self) -> dict:
        return redact_config(self._values)
