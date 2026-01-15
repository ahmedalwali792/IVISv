# FILE: ingestion/capture/rtsp_client.py
# ------------------------------------------------------------------------------
import os
import cv2
from ingestion.errors.fatal import FatalError  # ✅ FIX: Missing Import Added

class RTSPClient:
    def __init__(self, url):
        self.url = url
        self.cap = None
        self.is_file = False
        self.last_error = None

    def connect(self):
        try:
            url_int = int(self.url)
            self.cap = cv2.VideoCapture(url_int)
            self.is_file = False
        except ValueError:
            self.cap = cv2.VideoCapture(self.url)
            self.is_file = os.path.isfile(self.url)
        
        if not self.cap.isOpened():
            self.last_error = "open_failed"
            raise FatalError("Failed to open RTSP stream", context={"url": self.url})
        
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 0)
        self.last_error = None
    
    def get_raw_handle(self):
        if not self.cap:
            raise FatalError("Client not connected")
        return self.cap

    def close(self):
        if self.cap:
            self.cap.release()
            self.cap = None

    def reconnect(self) -> bool:
        self.close()
        try:
            self.connect()
            return True
        except FatalError:
            return False

    def rewind(self):
        if self.cap and self.is_file:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.cap.set(cv2.CAP_PROP_POS_MSEC, 0)

# ---------
