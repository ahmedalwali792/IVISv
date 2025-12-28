# FILE: ingestion/frame/anchor.py
# ------------------------------------------------------------------------------
import cv2
import numpy as np

class Anchor:
    def generate(self, frame):
        thumb = cv2.resize(frame, (8, 8), interpolation=cv2.INTER_NEAREST)
        gray = cv2.cvtColor(thumb, cv2.COLOR_RGB2GRAY)
        avg = gray.mean()
        bits = (gray > avg).flatten()
        pack = np.packbits(bits)
        hex_fingerprint = pack.tobytes().hex()
        return hex_fingerprint
