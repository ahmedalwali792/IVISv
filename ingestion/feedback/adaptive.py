# FILE: ingestion/feedback/adaptive.py
# ------------------------------------------------------------------------------
import json
import threading
import time


class AdaptiveRateController:
    def __init__(
        self,
        selector,
        min_fps: float,
        max_fps: float,
        safety_factor: float,
        ema_alpha: float = 0.2,
        hysteresis_ratio: float = 0.1,
        min_update_interval: float = 0.5,
        fps_smoothing: float = 0.3,
    ):
        self.selector = selector
        self.min_fps = max(1.0, float(min_fps))
        self.max_fps = max(self.min_fps, float(max_fps))
        self.safety = max(1.0, float(safety_factor))
        self.ema_alpha = min(1.0, max(0.01, float(ema_alpha)))
        self.hysteresis_ratio = min(0.5, max(0.0, float(hysteresis_ratio)))
        self.min_update_interval = max(0.0, float(min_update_interval))
        self.fps_smoothing = min(1.0, max(0.0, float(fps_smoothing)))
        self._last_update = 0.0
        self._ema_ms = None
        self._last_target_fps = None
        self._lock = threading.Lock()

    def _update_from_inference(self, inference_ms: float):
        if inference_ms <= 0:
            return
        now = time.perf_counter()
        with self._lock:
            if self._ema_ms is None:
                self._ema_ms = inference_ms
            else:
                self._ema_ms = (self.ema_alpha * inference_ms) + ((1.0 - self.ema_alpha) * self._ema_ms)

            target = 1000.0 / (self._ema_ms * self.safety)
            target = max(self.min_fps, min(self.max_fps, target))

            if self._last_target_fps is not None:
                target = self._last_target_fps + (target - self._last_target_fps) * self.fps_smoothing
                delta = abs(target - self._last_target_fps)
                if delta / max(self._last_target_fps, 1e-6) < self.hysteresis_ratio:
                    return
                if (now - self._last_update) < self.min_update_interval:
                    return

            self.selector.set_target_fps(target)
            self._last_target_fps = target
            self._last_update = now

    def _run_zmq(self, endpoint: str):
        try:
            import zmq
        except Exception:
            return
        ctx = zmq.Context.instance()
        socket = ctx.socket(zmq.SUB)
        socket.connect(endpoint)
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        while True:
            try:
                payload = socket.recv()
            except Exception:
                continue
            try:
                result = json.loads(payload.decode("utf-8"))
            except Exception:
                continue
            inference_ms = result.get("timing", {}).get("inference_ms")
            if inference_ms is not None:
                self._update_from_inference(float(inference_ms))

    def start(self, endpoint: str):
        if not endpoint:
            return
        thread = threading.Thread(target=self._run_zmq, args=(endpoint,), daemon=True)
        thread.start()
