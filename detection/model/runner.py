# FILE: detection/model/runner.py
# ------------------------------------------------------------------------------
import time
from typing import List, Dict, Any

import cv2
import numpy as np

from detection.metrics.counters import metrics
from detection.errors.fatal import FatalError
from detection.config import Config
from detection.tracking.reid_tracker import ReIDTracker


class ModelRunner:
    def __init__(self, model):
        self.model = model
        if not Config.REID_MODEL_PATH and not Config.REID_ALLOW_FALLBACK:
            raise FatalError(
                "REID_MODEL_PATH is required for visual fingerprint tracking",
                context={"env": "REID_MODEL_PATH"},
            )
        self.tracker = ReIDTracker(
            max_age=Config.TRACKER_MAX_AGE,
            init_frames=Config.TRACKER_INIT_FRAMES,
            nn_budget=Config.TRACKER_NN_BUDGET,
            max_iou=Config.TRACKER_MAX_IOU,
            model_name=Config.REID_MODEL_NAME,
            model_path=Config.REID_MODEL_PATH,
            allow_fallback=Config.REID_ALLOW_FALLBACK,
            half=Config.MODEL_HALF,
        )

    def warmup(self):
        dummy = np.zeros(self.model.input_shape(), dtype="uint8")
        self.model.predict(dummy)

    def infer(self, frame_bgr: np.ndarray) -> Dict[str, Any]:
        start = time.perf_counter()
        try:
            # Frames are expected to be in the contract color space (bgr) from ingestion.
            # Ingestion performs any needed source->bgr conversion, so do not
            # perform further color transforms here.
            model_start = time.perf_counter()
            raw_results = self.model.predict(frame_bgr)
            model_end = time.perf_counter()
            detections = self._parse_detections(raw_results)
            track_start = time.perf_counter()
            tracks = self.tracker.update(detections, frame_bgr)
            track_end = time.perf_counter()
            timing = {
                "inference_ms": (track_end - model_start) * 1000.0,
                "model_ms": (model_end - model_start) * 1000.0,
                "track_ms": (track_end - track_start) * 1000.0,
            }
            return {"detections": detections, "tracks": tracks, "timing": timing}
        except Exception as e:
            raise FatalError(f"Inference Engine Crash: {e}")
        finally:
            metrics.log_latency((time.perf_counter() - start) * 1000)

    def _parse_detections(self, raw_results) -> List[list]:
        detections = []
        try:
            if not raw_results:
                return detections
            result = raw_results[0]
            boxes = result.boxes
            if boxes is None:
                return detections
            for xyxy, conf, cls in zip(boxes.xyxy, boxes.conf, boxes.cls):
                x1, y1, x2, y2 = [float(v) for v in xyxy.tolist()]
                detections.append([[x1, y1, x2, y2], float(conf), int(cls)])
            return detections
        except Exception as exc:
            raise FatalError("Failed to parse model output", context={"error": str(exc)})
