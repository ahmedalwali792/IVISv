# FILE: ivis/common/time_utils.py
# ------------------------------------------------------------------------------
import time


def wall_clock_ms() -> int:
    return int(time.time() * 1000)


def monotonic_ms() -> int:
    return int(time.monotonic() * 1000)


def latency_ms(now_ms: int, timestamp_ms: int) -> int:
    return int(now_ms - timestamp_ms)
