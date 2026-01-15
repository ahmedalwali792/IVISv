# FILE: ingestion/frame/normalizer.py
# ------------------------------------------------------------------------------
import cv2


class Normalizer:
    def __init__(self, target_resolution, frame_color: str = "bgr"):
        self.target_size = target_resolution
        self.input_color = frame_color

    def process(self, raw_frame):
        frame = raw_frame
        if (frame.shape[1], frame.shape[0]) != self.target_size:
            frame = cv2.resize(frame, self.target_size, interpolation=cv2.INTER_NEAREST)
        if self.input_color == "rgb":
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        return frame
