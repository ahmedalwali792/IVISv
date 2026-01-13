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
	- `redis_lag`: approximate Redis stream length / lag.

Notes and usage:
- Each service runs its own Prometheus HTTP endpoint (or integrates into existing web server for UI). Configure your Prometheus scrape targets to collect metrics from these endpoints.
- Metric names and labels are intentionally short and consistent across services for easy aggregation.
- `frames_dropped_total` includes a `reason` label — useful for differentiating drops due to backpressure (`lag`) vs validation errors vs runtime exceptions.

Troubleshooting:
- If `/metrics` fails to bind, check the service logs for the "Prometheus metrics HTTP server started" message or exceptions about binding ports.
- The UI also provides a diagnostic JSON endpoint at `/json_metrics` with a quick snapshot of FPS and SHM status.

# Runbook — IVISv (Production Defaults)

Official bus: Redis Streams (production default)

- Producer: ingestion publishes frames to Redis Streams via `XADD` to the stream `ivis:frames`.
- Consumer (detection): uses `XREADGROUP` with consumer group `ivis:detection`.
- UI: consumes frames and results from Redis Streams (`ivis:frames`, `ivis:results`) by default.

Environment variables (important):

- `REDIS_URL` — e.g. `redis://localhost:6379/0`
- `REDIS_STREAM` — default `ivis:frames` (frames stream)
- `REDIS_RESULTS_STREAM` — default `ivis:results` (results stream)
- `REDIS_GROUP` — default `ivis:detection` (detection consumer group)
- `REDIS_CONSUMER` — consumer id for XREADGROUP (default `detector-1`)

Notes:

- The system defaults to Redis Streams (`XADD`/`XREADGROUP`), which provides at-least-once delivery semantics and backpressure handling for production workloads.
- Legacy transports (TCP socket, ZeroMQ proxy, Redis PubSub, dev HTTP memory server, etc.) have been moved to `ivis/legacy/` and are not part of the default path. They may still be used explicitly by setting `BUS_TRANSPORT` to a legacy value, but this is discouraged for production.
- If a consumer group does not exist, the detection consumer will attempt to create it with `mkstream=True`.

Quick commands:

Run system (default production mode — Redis Streams):

```bash
python run_system.py --source <rtsp-or-file> --redis-mode streams
```

Start a single service (example: detection):

```bash
python -m detection.main
```
