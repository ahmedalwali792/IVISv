# Result Contract V1

This document defines the ResultContractV1 emitted by the Detection service and consumed by UI.

Schema (JSON-like):

- `contract_version`: 1
- `frame_id`: string
- `stream_id`: string
- `camera_id`: string
- `timestamp_ms`: integer (ms)
- `mono_ms`: integer (ms)
- `detections`: array of objects {
  - `bbox`: [x1, y1, x2, y2] (numbers, XYXY)
  - `conf`: number (0.0 - 1.0)
  - `class_id`: integer
  - `class_name` (optional): string
  - `track_id` (optional): string or int
  }
- `model`: object {
  - `name`: string
  - `version`: string
  - `threshold`: number
  - `input_size`: [h, w]
  }
- `timing`: object {
  - `inference_ms`: number (required)
  - `ingest_ms` (optional): number
  - `total_ms` (optional): number
  }

Notes
- Consumers MUST validate the contract strictly. Any mismatch should be dropped and metrics incremented.
- The UI expects `detections` entries as objects (not positional tuples).
