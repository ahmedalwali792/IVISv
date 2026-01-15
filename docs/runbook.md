**Prometheus Metrics**

This runbook documents the Prometheus metrics exposed by IVIS services (ingestion, detection, UI).

Default endpoints and ports:
- Ingestion: `http://<host>:8001/metrics` or set `INGESTION_METRICS_PORT` env var.
- Detection: `http://<host>:8002/metrics` or set `DETECTION_METRICS_PORT` env var.
- UI: `http://<host>:8080/metrics` (exposed on the Flask UI service port).

Metric names (available across services):
- Counters:
	- `frames_in_total`: total frames entering a service.
	- `frames_out_total`: total frames successfully processed/published.
	- `frames_dropped_total{reason="..."}`: frames dropped, labeled by reason (`lag`, `validation_failed`, `nonfatal`, `unhandled_exception`, ...).
- Histograms (values observed in milliseconds):
	- `shm_write_latency_ms`: latency to write frames into shared memory.
	- `shm_read_latency_ms`: latency to read frames from shared memory.
	- `inference_latency_ms`: model inference time.
	- `end_to_end_latency_ms`: best-effort end-to-end latency from capture timestamp_ms to processing time.
- Gauges:
	- `fps_in`: approximate input fps (ingest if available).
	- `fps_out`: output/display fps (UI sets this value).

Notes and usage:
- Each service runs its own Prometheus HTTP endpoint (or integrates into existing web server for UI). Configure your Prometheus scrape targets to collect metrics from these endpoints.
- Metric names and labels are intentionally short and consistent across services for easy aggregation.
- `frames_dropped_total` includes a `reason` label — useful for differentiating drops due to backpressure (`lag`) vs validation errors vs runtime exceptions.

Troubleshooting:
- If `/metrics` fails to bind, check the service logs for the "Prometheus metrics HTTP server started" message or exceptions about binding ports.
- The UI also provides a diagnostic JSON endpoint at `/json_metrics` with a quick snapshot of FPS and SHM status.

# Runbook — IVISv (Production Defaults)

Official bus: ZeroMQ (contracts) + Shared Memory (frames)

- Producer: ingestion publishes frame contracts over ZeroMQ and writes frame bytes to SHM ring.
- Consumer (detection): subscribes to contracts over ZeroMQ and reads frame bytes from SHM.
- UI: subscribes to contracts/results over ZeroMQ and renders frames from SHM.

Environment variables (important):

- `ZMQ_PUB_ENDPOINT` — publisher endpoint for frame contracts (ingestion).
- `ZMQ_SUB_ENDPOINT` — subscriber endpoint for frame contracts (detection/UI).
- `ZMQ_RESULTS_PUB_ENDPOINT` — publisher endpoint for results (detection).
- `ZMQ_RESULTS_SUB_ENDPOINT` — subscriber endpoint for results (UI/ingestion adaptive).
- `SHM_CACHE_SECONDS` — how many seconds to keep in the SHM ring cache.

Notes:

- The system defaults to ZeroMQ for contract delivery and SHM for frame bytes.
- Legacy transports (TCP socket, dev-only proxies) remain under `ivis/legacy/` and are not part of the default path.

Quick commands:

Run system (default production mode — ZMQ + SHM):

```bash
python run_system.py --source <rtsp-or-file>
```

Start a single service (example: detection):

```bash
python -m detection.main
```
