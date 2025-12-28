# ------------------------------------------------------------------------------
# FILE: ingestion/config.py
# ------------------------------------------------------------------------------
import os

from ingestion.errors.fatal import ConfigError


class Config:
    def __init__(self):
        self.rtsp_url = self._get_env("RTSP_URL")
        self.stream_id = self._get_env("STREAM_ID")
        self.camera_id = self._get_env("CAMERA_ID")
        self.target_fps = int(self._get_env("TARGET_FPS"))
        
        self.frame_width = int(self._get_env("FRAME_WIDTH"))
        self.frame_height = int(self._get_env("FRAME_HEIGHT"))
        
        self.memory_backend = self._get_env("MEMORY_BACKEND") 

        self._validate()

    def _get_env(self, key):
        val = os.getenv(key)
        if val is None:
            raise ConfigError("Missing required environment variable", context={"missing_key": key})
        return val

    def _validate(self):
        if self.target_fps <= 0:
            raise ConfigError("Invalid TARGET_FPS", context={"value": self.target_fps})
        if self.frame_width <= 0 or self.frame_height <= 0:
            raise ConfigError("Invalid resolution", context={"w": self.frame_width, "h": self.frame_height})

    @property
    def resolution(self):
        return (self.frame_width, self.frame_height)
