# FILE: ingestion/capture/reconnect.py
# ------------------------------------------------------------------------------
import random
import time
from typing import Optional


class ReconnectController:
    def __init__(
        self,
        min_delay: float,
        max_delay: float,
        factor: float = 2.0,
        jitter: float = 0.1,
        max_retries: int = 0,
    ):
        self.min_delay = max(0.0, float(min_delay))
        self.max_delay = max(self.min_delay, float(max_delay))
        self.factor = max(1.0, float(factor))
        self.jitter = max(0.0, float(jitter))
        self.max_retries = int(max_retries)
        self._attempts = 0

    def reset(self) -> None:
        self._attempts = 0

    @property
    def attempts(self) -> int:
        return self._attempts

    def _next_delay(self) -> Optional[float]:
        if self.max_retries > 0 and self._attempts >= self.max_retries:
            return None
        base = self.min_delay * (self.factor ** self._attempts)
        base = min(self.max_delay, base)
        self._attempts += 1
        if self.jitter:
            base += random.uniform(-self.jitter, self.jitter) * base
        return max(0.0, base)

    def wait(self) -> Optional[float]:
        delay = self._next_delay()
        if delay is None:
            return None
        time.sleep(delay)
        return delay
