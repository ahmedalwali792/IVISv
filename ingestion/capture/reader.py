# FILE: ingestion/capture/reader.py
# ------------------------------------------------------------------------------
import cv2

from ivis.common.time_utils import monotonic_ms, wall_clock_ms

class FramePacket:
    def __init__(self, payload, pts, timestamp_ms, mono_ms):
        self.payload = payload
        self.pts = pts
        self.timestamp_ms = timestamp_ms
        self.mono_ms = mono_ms

class Reader:
    def __init__(self, rtsp_client):
        self.client = rtsp_client
        self._last_pts = 0.0

    def next_packet(self):
        cap = self.client.get_raw_handle()
        try:
            ret, raw_data = cap.read()
        except Exception:
            return None
        
        if not ret:
            return None

        wall_clock = wall_clock_ms()
        mono_clock = monotonic_ms()
        pts_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
        if pts_ms <= 0:
            pts_ms = wall_clock
        if pts_ms <= 0:
            pts_ms = self._last_pts + 1.0
        self._last_pts = pts_ms
        
        return FramePacket(payload=raw_data, pts=pts_ms, timestamp_ms=wall_clock, mono_ms=mono_clock)
