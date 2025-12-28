# FILE: ingestion/capture/rtsp_client.py
# ------------------------------------------------------------------------------
import cv2
from ingestion.errors.fatal import FatalError  # ✅ FIX: Missing Import Added

class RTSPClient:
    def __init__(self, url):
        self.url = url
        self.cap = None

    def connect(self):
        try:
            url_int = int(self.url)
            self.cap = cv2.VideoCapture(url_int)
        except ValueError:
            self.cap = cv2.VideoCapture(self.url)
        
        if not self.cap.isOpened():
            raise FatalError("Failed to open RTSP stream", context={"url": self.url})
        
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 0)
    
    def get_raw_handle(self):
        if not self.cap:
            raise FatalError("Client not connected")
        return self.cap

    def close(self):
        if self.cap:
            self.cap.release()

# ---------