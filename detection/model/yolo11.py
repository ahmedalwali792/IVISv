# FILE: detection/model/yolo11.py
# ------------------------------------------------------------------------------
import os
from typing import Optional

import numpy as np

from detection.errors.fatal import FatalError
from detection.model.base import BaseModel


class Yolo11Model(BaseModel):
    def __init__(
        self,
        model_path: str,
        device: str = "auto",
        half: bool = False,
        img_size: int = 640,
        conf: float = 0.25,
        iou: float = 0.5,
    ) -> None:
        self.model_path = model_path
        self.device = device
        self.half = half
        self.img_size = img_size
        self.conf = conf
        self.iou = iou
        self._model = None
        self._device_resolved: Optional[str] = None

    def load(self):
        if not self.model_path:
            raise FatalError("MODEL_PATH is empty", context={"env": "MODEL_PATH"})
        if not os.path.exists(self.model_path):
            raise FatalError("Model file not found", context={"path": self.model_path})

        try:
            import torch
            from ultralytics import YOLO
        except Exception as exc:
            raise FatalError("Missing Ultralytics/Torch dependency", context={"error": str(exc)}) from exc

        thread_count = os.getenv("TORCH_NUM_THREADS")
        interop_threads = os.getenv("TORCH_NUM_INTEROP_THREADS")
        if thread_count:
            try:
                torch.set_num_threads(int(thread_count))
            except ValueError:
                pass
        if interop_threads:
            try:
                torch.set_num_interop_threads(int(interop_threads))
            except ValueError:
                pass

        if self.device == "auto":
            self._device_resolved = "cuda:0" if torch.cuda.is_available() else "cpu"
        else:
            self._device_resolved = self.device

        self._model = YOLO(self.model_path)
        self._model.to(self._device_resolved)
        if self.half and self._device_resolved.startswith("cuda"):
            self._model.model.half()

    def input_shape(self):
        return (self.img_size, self.img_size, 3)

    def predict(self, input_tensor: np.ndarray):
        if self._model is None:
            raise FatalError("Model not loaded")

        return self._model.predict(
            source=input_tensor,
            imgsz=self.img_size,
            conf=self.conf,
            iou=self.iou,
            device=self._device_resolved,
            verbose=False,
        )
