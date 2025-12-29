# [2025-12-29] results/config.py
import os
import sys

class Config:
    def __init__(self):
        self.transport_type = os.getenv("TRANSPORT_TYPE", "simple")
        self.bus_host = self._req("BUS_HOST")
        self.bus_port = int(self._req("BUS_PORT"))
        self.output_topic = self._req("OUTPUT_TOPIC")
        self.log_file = os.getenv("RESULT_LOG_FILE", "detections.jsonl")
        self.canvas_width = int(os.getenv("FRAME_WIDTH", 640))
        self.canvas_height = int(os.getenv("FRAME_HEIGHT", 480))

    def _req(self, key):
        val = os.getenv(key)
        if val is None:
            print(f"FATAL: Missing env {key}")
            sys.exit(1)
        return val