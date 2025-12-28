# FILE: detection/postprocess/parse.py
# ------------------------------------------------------------------------------
def parse_output(frame_id, raw_detections):
    return {
        "frame_id": frame_id,
        "detections": raw_detections,
        "timestamp": 0
    }
