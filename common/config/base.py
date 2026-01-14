# FILE: common/config/base.py
# ------------------------------------------------------------------------------
import os
import warnings
from typing import Any, Dict, Optional


class ConfigLoadError(Exception):
    pass


def _parse_bool(raw: str) -> bool:
    if raw.lower() in ("true", "1", "yes", "y"):
        return True
    if raw.lower() in ("false", "0", "no", "n"):
        return False
    raise ValueError(f"Invalid boolean value: {raw}")


_TYPE_PARSERS = {
    "str": str,
    "int": int,
    "float": float,
    "bool": _parse_bool,
}


class EnvLoader:
    def __init__(self, env: Optional[Dict[str, str]] = None):
        # Prefer an explicit env mapping; otherwise merge real env with centralized SETTINGS
        if env is not None:
            self.env = env
        else:
            # Start from the real process environment. Centralized SETTINGS
            # provide defaults only; explicit environment variables must take
            # precedence. Therefore we merge SETTINGS.as_env() into the
            # environment but do not overwrite existing keys.
            merged = dict(os.environ)
            try:
                from common.settings import SETTINGS

                defaults = SETTINGS.as_env()
                for k, v in defaults.items():
                    if k not in merged:
                        merged[k] = v
            except Exception as exc:
                warnings.warn(f"Failed to load SETTINGS defaults: {exc}", RuntimeWarning)
            self.env = merged

    def load(self, schema: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        for key, spec in schema.items():
            raw = self.env.get(key)
            typ = spec.get("type", "str")
            default = spec.get("default")
            required = bool(spec.get("required", False))
            parser = _TYPE_PARSERS.get(typ)
            if parser is None:
                raise ConfigLoadError(f"Unsupported type '{typ}' for {key}")
            if raw is None:
                if required and default is None:
                    raise ConfigLoadError(f"Missing required env var: {key}")
                values[key] = parser(str(default)) if default is not None else None
                continue
            try:
                values[key] = parser(raw)
            except Exception as exc:
                raise ConfigLoadError(f"Invalid {typ} env var {key}: {raw}") from exc
        return values


_REDACT_KEYS = {"POSTGRES_DSN", "REDIS_URL"}
_REDACT_HINTS = ("PASSWORD", "SECRET", "TOKEN", "DSN")


def _should_redact(key: str) -> bool:
    if key in _REDACT_KEYS:
        return True
    upper = key.upper()
    return any(hint in upper for hint in _REDACT_HINTS)


def redact_config(values: Dict[str, Any]) -> Dict[str, Any]:
    sanitized: Dict[str, Any] = {}
    for key, value in values.items():
        if _should_redact(key) and value is not None:
            sanitized[key] = "****"
        else:
            sanitized[key] = value
    return sanitized
