# FILE: detection/preprocess/tensorize.py
# ------------------------------------------------------------------------------
import numpy as np

def to_model_input(frame_data: np.ndarray) -> np.ndarray:
    tensor = frame_data.astype("float32") / 255.0
    return tensor[None, ...]
