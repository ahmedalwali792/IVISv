import json
import logging
import os
from logging.handlers import RotatingFileHandler

_STANDARD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "service": record.name,
            "message": record.getMessage(),
        }
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_ATTRS
        }
        # Ensure mandatory structured fields are present (may be None)
        mandatory = ["stream_id", "frame_id", "generation", "latency_ms", "error_code"]
        for m in mandatory:
            payload[m] = extras.get(m) if extras.get(m) is not None else None

        # merge any other extras
        if extras:
            payload.update(extras)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_ATTRS
        }
        if extras:
            extra_pairs = " ".join(f"{key}={value}" for key, value in extras.items())
            msg = f"{msg} | {extra_pairs}"
        return msg


def setup_logging(service_name: str = "ivis") -> logging.Logger:
    logs_dir = os.getenv("LOG_DIR") or os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)

    logger = logging.getLogger(service_name)
    if logger.handlers:
        return logger

    debug = os.getenv("DEBUG", "false").lower() == "true"
    level = logging.DEBUG if debug else logging.INFO

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    log_format = os.getenv("LOG_FORMAT", "text").lower()
    if log_format == "json":
        formatter = JsonFormatter()
    else:
        formatter = TextFormatter(fmt)

    # Stream handler (stdout)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    sh.setLevel(level)
    logger.addHandler(sh)

    # Rotating file handler
    fh_path = os.path.join(logs_dir, f"{service_name}.log")
    fh = RotatingFileHandler(fh_path, maxBytes=5 * 1024 * 1024, backupCount=3)
    fh.setFormatter(formatter)
    fh.setLevel(level)
    logger.addHandler(fh)

    logger.setLevel(level)
    logger.propagate = False
    return logger
