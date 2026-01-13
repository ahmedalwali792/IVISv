# FILE: detection/postprocess/parse.py
# ------------------------------------------------------------------------------

def _iou(box_a, box_b):
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter_area
    if denom <= 0:
        return 0.0
    return inter_area / denom


def _track_bbox_xyxy(track: dict):
    tb = track.get("bbox_xyxy")
    if tb and isinstance(tb, (list, tuple)) and len(tb) == 4:
        try:
            return [float(tb[0]), float(tb[1]), float(tb[2]), float(tb[3])]
        except Exception:
            return None
    tb = track.get("bbox")
    if tb and isinstance(tb, (list, tuple)) and len(tb) == 4:
        try:
            x, y, w, h = [float(v) for v in tb]
        except Exception:
            return None
        return [x, y, x + max(0.0, w), y + max(0.0, h)]
    return None


def parse_output(frame_contract: dict, raw_results: dict):
    """Construct ResultContractV1 from frame contract and raw model/tracker outputs.

    Detections list entries are normalized to include optional track_id when available.
    """
    timing = raw_results.get("timing") or {}
    timing.setdefault("inference_ms", 0.0)

    raw_dets = raw_results.get("detections", [])
    raw_tracks = raw_results.get("tracks", [])

    tracks = []
    for t in raw_tracks:
        tb = _track_bbox_xyxy(t)
        if tb is not None:
            tracks.append((t, tb))

    dets = []
    unused = set(range(len(tracks)))
    for det in raw_dets:
        try:
            (x1, y1, x2, y2), conf, cls_id = det
        except Exception:
            continue
        entry = {
            "bbox": [float(x1), float(y1), float(x2), float(y2)],
            "conf": float(conf),
            "class_id": int(cls_id),
        }
        best_idx = None
        best_iou = 0.0
        for idx in list(unused):
            _, tb = tracks[idx]
            iou = _iou(entry["bbox"], tb)
            if iou > best_iou:
                best_iou = iou
                best_idx = idx
        if best_idx is not None and best_iou >= 0.3:
            track_id = tracks[best_idx][0].get("track_id")
            if track_id is not None:
                entry["track_id"] = track_id
            unused.discard(best_idx)
        dets.append(entry)

    result = {
        "contract_version": 1,
        "frame_id": frame_contract["frame_id"],
        "stream_id": frame_contract["stream_id"],
        "camera_id": frame_contract["camera_id"],
        "timestamp_ms": frame_contract["timestamp_ms"],
        "mono_ms": frame_contract["mono_ms"],
        "detections": dets,
        "model": {},
        "timing": timing,
    }

    return result
