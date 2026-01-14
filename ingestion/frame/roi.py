# FILE: ingestion/frame/roi.py
# ------------------------------------------------------------------------------
from typing import List, Optional, Tuple

import cv2
import numpy as np


def _parse_ints(values: List[str]) -> List[int]:
    parsed = []
    for val in values:
        if val is None:
            continue
        v = val.strip()
        if not v:
            continue
        parsed.append(int(float(v)))
    return parsed


def parse_boxes(raw: Optional[str]) -> List[Tuple[int, int, int, int]]:
    if not raw:
        return []
    boxes = []
    for part in raw.split(";"):
        nums = _parse_ints(part.split(","))
        if len(nums) != 4:
            continue
        x1, y1, x2, y2 = nums
        if x2 <= x1 or y2 <= y1:
            continue
        boxes.append((x1, y1, x2, y2))
    return boxes


def parse_polygons(raw: Optional[str]) -> List[List[Tuple[int, int]]]:
    if not raw:
        return []
    polygons = []
    for poly_raw in raw.split("|"):
        points = []
        for point_raw in poly_raw.split(";"):
            nums = _parse_ints(point_raw.split(","))
            if len(nums) != 2:
                continue
            points.append((nums[0], nums[1]))
        if len(points) >= 3:
            polygons.append(points)
    return polygons


def build_mask(width: int, height: int, boxes, polygons):
    if not boxes and not polygons:
        return None
    mask = np.zeros((height, width), dtype=np.uint8)
    for x1, y1, x2, y2 in boxes:
        cv2.rectangle(mask, (x1, y1), (x2, y2), 255, thickness=-1)
    for polygon in polygons:
        pts = np.array(polygon, dtype=np.int32)
        cv2.fillPoly(mask, [pts], 255)
    return mask


def apply_mask(frame, mask):
    if mask is None:
        return frame
    return cv2.bitwise_and(frame, frame, mask=mask)
