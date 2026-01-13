# FILE: ui/results_cache.py
# ------------------------------------------------------------------------------
import time
from collections import OrderedDict
from typing import Any, Callable, Optional


class ResultsCache:
    def __init__(
        self,
        max_entries: int = 2000,
        ttl_seconds: float = 60.0,
        time_fn: Optional[Callable[[], float]] = None,
    ) -> None:
        self._max_entries = max(1, int(max_entries))
        self._ttl_seconds = float(ttl_seconds)
        self._time_fn = time_fn or time.monotonic
        self._data = OrderedDict()

    def __len__(self) -> int:
        return len(self._data)

    def _is_expired(self, now: float, timestamp: float) -> bool:
        if self._ttl_seconds <= 0:
            return False
        return (now - timestamp) > self._ttl_seconds

    def _purge_expired(self, now: float) -> None:
        if self._ttl_seconds <= 0 or not self._data:
            return
        expired_keys = [key for key, (ts, _) in self._data.items() if self._is_expired(now, ts)]
        for key in expired_keys:
            self._data.pop(key, None)

    def get(self, key: str) -> Optional[Any]:
        now = self._time_fn()
        entry = self._data.get(key)
        if entry is None:
            return None
        ts, value = entry
        if self._is_expired(now, ts):
            self._data.pop(key, None)
            return None
        self._data.pop(key, None)
        self._data[key] = (now, value)
        return value

    def put(self, key: str, value: Any) -> None:
        now = self._time_fn()
        if key in self._data:
            self._data.pop(key, None)
        self._data[key] = (now, value)
        self._purge_expired(now)
        while len(self._data) > self._max_entries:
            self._data.popitem(last=False)
