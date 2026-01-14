# Frame Contract v1

This document defines the FrameContractV1 payload for ingestion -> detection -> UI.

## Fields

- contract_version (int): must be 1.
- frame_id (string): unique frame identifier derived from stream_id + pts + fingerprint.
- stream_id (string): stream identifier.
- camera_id (string): camera identifier.
- pts (float): presentation timestamp in milliseconds from the source when available.
- timestamp_ms (int): wall-clock epoch time in milliseconds at capture.
- mono_ms (int): monotonic clock time in milliseconds at capture (must not go backwards).
- memory (object):
  - backend (string): backend identifier (e.g., shm_ring_v1).
  - key (string): slot key in the backend.
  - size (int): payload size in bytes.
  - generation (int): slot generation for eviction safety.
- frame_width (int): width in pixels.
- frame_height (int): height in pixels.
- frame_channels (int): channel count (v1 expects 3).
- frame_dtype (string): data type (v1 expects uint8).
- frame_color_space (string): color space (v1 expects bgr).
- roi (object, optional): region-of-interest metadata.
  - boxes: list of [x1, y1, x2, y2].
  - polygons: list of point lists, each point is [x, y].

## Timestamp discipline

- timestamp_ms is wall clock and can jump if the system time changes.
- mono_ms is monotonic and must never decrease; use it for durations and latency.
- pts reflects the source timeline and can reset (e.g., file rewind).
