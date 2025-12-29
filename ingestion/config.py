# [2025-12-29] ingestion/config.py
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
        
        # Transport Config (Stage 5 Update)
        self.transport_type = os.getenv("TRANSPORT_TYPE", "simple")
        self.bus_host = self._get_env("BUS_HOST")
        self.bus_port = int(self._get_env("BUS_PORT"))

        self._validate()

    def _get_env(self, key):
        val = os.getenv(key)
        if val is None:
            raise ConfigError("Missing required environment variable", context={"missing_key": key})
        return val

    def _validate(self):
        if self.target_fps <= 0:
            raise ConfigError("Invalid TARGET_FPS", context={"value": self.target_fps})

    @property
    def resolution(self):
        return (self.frame_width, self.frame_height)