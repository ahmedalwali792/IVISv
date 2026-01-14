# FILE: ingestion/feedback/lag_controller.py
# ------------------------------------------------------------------------------


class LagBasedRateController:
    def __init__(
        self,
        selector,
        min_fps: float,
        max_fps: float,
        lag_threshold: int,
        hysteresis_ratio: float = 0.2,
    ):
        self.selector = selector
        self.min_fps = max(1.0, float(min_fps))
        self.max_fps = max(self.min_fps, float(max_fps))
        self.lag_threshold = max(0, int(lag_threshold))
        self.hysteresis_ratio = max(0.0, min(0.9, float(hysteresis_ratio)))
        self._lagged = False

    def update(self, lag_value: int) -> bool:
        if self.lag_threshold <= 0:
            return False
        try:
            lag = int(lag_value)
        except (TypeError, ValueError):
            return False

        if self._lagged:
            recover_at = int(self.lag_threshold * (1.0 - self.hysteresis_ratio))
            if lag <= recover_at:
                self.selector.set_lag_cap(None)
                self._lagged = False
                return True
            self.selector.set_lag_cap(self.min_fps)
            return False

        if lag >= self.lag_threshold:
            self.selector.set_lag_cap(self.min_fps)
            self._lagged = True
            return True
        return False
