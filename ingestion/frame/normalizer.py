# FILE: ingestion/frame/normalizer.py
# ------------------------------------------------------------------------------
import cv2

class Normalizer:
    def __init__(self, target_resolution):
        self.target_size = target_resolution

    def process(self, raw_frame):
        frame = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2RGB)
        if (frame.shape[1], frame.shape[0]) != self.target_size:
            frame = cv2.resize(frame, self.target_size, interpolation=cv2.INTER_NEAREST)
        return frame
