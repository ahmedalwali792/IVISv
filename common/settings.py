"""Centralized application settings using Pydantic (with graceful fallback).

This module exposes a single `SETTINGS` object with nested sections. It
prefers `pydantic-settings` when available, but will fall back to a small
compat shim that reads environment variables. It also implements the
FRAME_COLOR -> SOURCE_COLOR migration with a warning.
"""
from __future__ import annotations

import os
import warnings
from typing import Optional, Literal

try:
    from pydantic_settings import BaseSettings
    from pydantic import Field
except Exception:
    # Minimal fallback using pydantic BaseModel if pydantic-settings isn't installed.
    try:
        from pydantic import BaseModel as BaseSettings, Field
    except Exception:  # pragma: no cover - extremely unlikely in project env
        class BaseSettings(object):
            pass


class SystemSettings(BaseSettings):
    app_name: str = Field("ivis")
    env_file: Optional[str] = Field(".env")
    # FRAME_COLOR_SPACE is a fixed contract for v1 and must be 'bgr'
    frame_color_space: Literal["bgr"] = Field("bgr")


class IngestionSettings(BaseSettings):
    # SOURCE_COLOR: color of the source camera/input. Ingestion will convert
    # from SOURCE_COLOR -> FRAME_COLOR_SPACE before publishing frames.
    source_color: Literal["bgr", "rgb"] = Field("bgr")
    frame_width: int = Field(640)
    frame_height: int = Field(480)
    shm_name: str = Field("ivis_shm_data")
    shm_meta_name: str = Field("ivis_shm_meta")
    shm_buffer_bytes: int = Field(50000000)
    shm_cache_seconds: float = Field(30.0)
    target_fps: int = Field(15)
    video_loop: bool = Field(False)


class DetectionSettings(BaseSettings):
    frame_width: int = Field(640)
    frame_height: int = Field(480)
    # Downstream services should assume FRAME_COLOR_SPACE (bgr) and not
    # perform further conversions.


class UISettings(BaseSettings):
    frame_width: int = Field(640)
    frame_height: int = Field(480)


class PostgresSettings(BaseSettings):
    dsn: Optional[str] = Field(None)


class LoggingSettings(BaseSettings):
    level: str = Field("INFO")
    log_dir: Optional[str] = Field(None)


class MetricsSettings(BaseSettings):
    enabled: bool = Field(True)


class TracingSettings(BaseSettings):
    enabled: bool = Field(False)


class Settings(BaseSettings):
    system: SystemSettings = SystemSettings()
    ingestion: IngestionSettings = IngestionSettings()
    detection: DetectionSettings = DetectionSettings()
    ui: UISettings = UISettings()
    postgres: PostgresSettings = PostgresSettings()
    logging: LoggingSettings = LoggingSettings()
    metrics: MetricsSettings = MetricsSettings()
    tracing: TracingSettings = TracingSettings()

    # Legacy detection: if FRAME_COLOR is present in the environment, treat it
    # as the source color (for ingestion) but keep FRAME_COLOR_SPACE == bgr.
    def apply_legacy_migration(self):
        legacy = os.getenv("FRAME_COLOR")
        if legacy:
            leg = legacy.lower()
            if leg in ("rgb", "bgr"):
                warnings.warn(
                    "Environment variable FRAME_COLOR is deprecated; mapped to SOURCE_COLOR for ingestion. "
                    "Downstream FRAME_COLOR_SPACE remains 'bgr' (v1 contract).",
                    DeprecationWarning,
                )
                # Map legacy FRAME_COLOR to ingestion.source_color
                self.ingestion.source_color = leg  # type: ignore

    def as_env(self) -> dict:
        """Return a simple env mapping for backward-compatible EnvLoader use.

        Values are strings as environment variables would be.
        """
        env = {}
        env["FRAME_COLOR_SPACE"] = self.system.frame_color_space
        env["SOURCE_COLOR"] = self.ingestion.source_color
        env["FRAME_WIDTH"] = str(self.ingestion.frame_width)
        env["FRAME_HEIGHT"] = str(self.ingestion.frame_height)
        env["SHM_NAME"] = self.ingestion.shm_name
        env["SHM_META_NAME"] = self.ingestion.shm_meta_name
        env["SHM_BUFFER_BYTES"] = str(self.ingestion.shm_buffer_bytes)
        env["SHM_CACHE_SECONDS"] = str(self.ingestion.shm_cache_seconds)
        env["TARGET_FPS"] = str(self.ingestion.target_fps)
        env["VIDEO_LOOP"] = "1" if self.ingestion.video_loop else "0"
        return env


# instantiate global settings and apply migration
SETTINGS = Settings()
try:
    SETTINGS.apply_legacy_migration()
except Exception as exc:
    warnings.warn(f"Failed to apply legacy settings migration: {exc}", RuntimeWarning)
