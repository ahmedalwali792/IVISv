# FILE: detection/model/loader.py
# ------------------------------------------------------------------------------
import os

from detection.config import Config
from detection.model.base import BaseModel
from detection.model.yolo11 import Yolo11Model
from detection.errors.fatal import FatalError

def load_model() -> BaseModel:
    try:
        # Ensure MODEL_PATH exists and is readable
        model_path = Config.MODEL_PATH
        if not model_path:
            raise FatalError("MODEL_PATH is empty", context={"env": "MODEL_PATH"})

        if not os.path.isabs(model_path):
            # Resolve relative paths against project root
            model_path = os.path.abspath(model_path)

        if not os.path.exists(model_path):
            raise FatalError("Model file not found", context={"path": model_path})

        model = Yolo11Model(
            model_path=model_path,
            device=Config.MODEL_DEVICE,
            half=Config.MODEL_HALF,
            img_size=Config.MODEL_IMG_SIZE,
            conf=Config.MODEL_CONF,
            iou=Config.MODEL_IOU,
        )
        model.load()
        return model
    except Exception as e:
        # If already a FatalError, re-raise with context preserved
        if isinstance(e, FatalError):
            raise
        raise FatalError("Model load failed", context={"error": str(e)})
