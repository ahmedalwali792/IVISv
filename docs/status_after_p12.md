# Status after P12

## pytest
- Command: `python -m pytest -q`
- Result: `5 passed in 0.67s`

## Local run (15s)
- Redis: running locally (redis-server process already active); publish failed with `MISCONF ... stop-writes-on-bgsave-error` (see `logs/ingestion.err`).
- Command: `python run_system.py --source sample.mp4` (note: `--rtsp-url` is not a recognized flag in `run_system.py`).
- Runtime: ~15s; UI health reachable.
- Streams:
  - Redis streams: `ivis:frames`, `ivis:results`
  - Contract stream_id: `cam_01_main` (camera_id `cam_01`)

## Contract validation drops
- Not observed in this run (no validation logs in `logs/ingestion.err`, `logs/detection.err`, `logs/ui.err`; detection metrics had no `frames_dropped_total{reason="validation_failed"}` samples).

## Health/Metrics snapshots (brief)
- Ingestion (`http://127.0.0.1:8001/metrics`):
  - `frames_in_total 238`
  - `frames_out_total 0`
  - `frames_dropped_total{reason="lag"} 31`
  - `shm_write_latency_ms_count 31` / `shm_write_latency_ms_sum 28.014421463012695`
  - `/health` not exposed
- Detection (`http://127.0.0.1:8002/metrics`):
  - `frames_in_total 0`
  - `frames_out_total 0`
  - `fps_in 0` / `fps_out 0`
  - `frames_dropped_total` has no samples
  - `/health` not exposed
- UI (`http://127.0.0.1:8080/health`):
  - `{"status":"ok"}`
- UI (`http://127.0.0.1:8080/metrics`):
  - `frames_in_total 0`
  - `frames_out_total 0`
  - `shm_read_latency_ms_count 1503` / `shm_read_latency_ms_sum 116.99652671813965`
  - `fps_out 346.37539272700997`

## Notes
- Ingestion could not publish to Redis due to `MISCONF` (RDB snapshot write failure), so detection saw 0 frames.
