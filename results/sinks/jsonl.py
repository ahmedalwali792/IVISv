# [2025-12-29] results/sinks/jsonl.py
import json
import sys
from results.sinks.base import BaseSink

class JsonlSink(BaseSink):
    def __init__(self, filepath):
        self.filepath = filepath
        try:
            with open(self.filepath, 'a') as f: pass
        except Exception as e:
            print(f"FATAL: Log file error: {e}"); sys.exit(1)

    def handle(self, result: dict):
        try:
            with open(self.filepath, 'a') as f:
                f.write(json.dumps(result) + "\n")
        except: sys.exit(1)