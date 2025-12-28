# FILE: ingestion/capture/reader.py
# ------------------------------------------------------------------------------
import cv2
import time

class FramePacket:
    def __init__(self, payload, pts, wall_clock_ms):
        self.payload = payload
        self.pts = pts
        self.timestamp = wall_clock_ms

class Reader:
    def __init__(self, rtsp_client):
        self.client = rtsp_client

    def next_packet(self):
        cap = self.client.get_raw_handle()
        ret, raw_data = cap.read()
        
        if not ret:
            return None

        pts_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
        wall_clock = int(time.time() * 1000)
        
        return FramePacket(payload=raw_data, pts=pts_ms, wall_clock_ms=wall_clock)
