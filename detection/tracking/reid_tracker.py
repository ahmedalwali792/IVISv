# FILE: detection/tracking/reid_tracker.py
# ------------------------------------------------------------------------------
import hashlib
from typing import List, Dict, Any

import numpy as np

from detection.errors.fatal import FatalError


class ReIDTracker:
    def __init__(
        self,
        max_age: int,
        init_frames: int,
        nn_budget: int,
        max_iou: float,
        model_name: str,
        model_path: str = None,
        allow_fallback: bool = False,
        half: bool = False,
    ) -> None:
        try:
            from deep_sort_realtime.deepsort_tracker import DeepSort
        except Exception as exc:
            raise FatalError("Missing DeepSORT dependency", context={"error": str(exc)}) from exc

        use_fallback = allow_fallback and not model_path
        if use_fallback:
            kwargs = {
                "max_age": max_age,
                "n_init": init_frames,
                "nn_budget": nn_budget,
                "max_iou_distance": max_iou,
                "embedder": "mobilenet",
                "half": half,
                "bgr": True,
            }
        else:
            kwargs = {
                "max_age": max_age,
                "n_init": init_frames,
                "nn_budget": nn_budget,
                "max_iou_distance": max_iou,
                "embedder": "torchreid",
                "embedder_model_name": model_name,
                "half": half,
                "bgr": True,
            }
            if model_path:
                kwargs["embedder_wts"] = model_path

        self._tracker = DeepSort(**kwargs)

    def update(self, detections: List[list], frame_bgr: np.ndarray) -> List[Dict[str, Any]]:
        tracks = self._tracker.update_tracks(detections, frame=frame_bgr)
        output = []
        for track in tracks:
            if not track.is_confirmed():
                continue
            if hasattr(track, "to_ltrb"):
                left, top, right, bottom = track.to_ltrb()
            elif hasattr(track, "to_tlbr"):
                left, top, right, bottom = track.to_tlbr()
            else:
                continue

            feature = getattr(track, "last_feature", None)
            appearance_hash = None
            if feature is not None:
                try:
                    digest = hashlib.sha1(np.asarray(feature).tobytes()).hexdigest()
                    appearance_hash = digest
                except Exception:
                    appearance_hash = None

            output.append(
                {
                    "track_id": track.track_id,
                    "bbox": [float(left), float(top), float(right - left), float(bottom - top)],
                    "bbox_xyxy": [float(left), float(top), float(right), float(bottom)],
                    "confidence": float(getattr(track, "det_conf", 0.0) or 0.0),
                    "class_id": int(getattr(track, "det_class", -1) or -1),
                    "appearance_hash": appearance_hash,
                }
            )
        return output
