from prometheus_client import Counter, Histogram, Gauge, start_http_server, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
from prometheus_client import REGISTRY
from flask import Response
import time

# Prometheus metrics (shared names across services - each service runs separately)
frames_in_total = Counter("frames_in_total", "Total frames entering the pipeline")
frames_out_total = Counter("frames_out_total", "Total frames successfully processed/published")
frames_dropped_total = Counter("frames_dropped_total", "Total frames dropped", ["reason"])
drops_total = Counter("drops_total", "Dropped frames", ["reason"])
service_errors_total = Counter("service_errors_total", "Service errors", ["service", "reason"])

# Latency metrics (measured in milliseconds)
shm_write_latency_ms = Histogram("shm_write_latency_ms", "SHM write latency (ms)")
shm_read_latency_ms = Histogram("shm_read_latency_ms", "SHM read latency (ms)")
shm_bytes_copied_total = Counter("shm_bytes_copied_total", "Total bytes copied via SHM")
inference_latency_ms = Histogram("inference_latency_ms", "Inference latency (ms)")
end_to_end_latency_ms = Histogram("end_to_end_latency_ms", "End-to-end latency (ms)")

# Gauges
fps_in = Gauge("fps_in", "Input frames per second (approx)")
fps_out = Gauge("fps_out", "Output frames per second (displayed)")
redis_lag = Gauge("redis_lag", "Approximate Redis stream length / lag")
adaptive_fps_current = Gauge("adaptive_fps_current", "Current adaptive FPS target")
ui_results_cache_size = Gauge("ui_results_cache_size", "UI results cache size")
record_buffer_size = Gauge("record_buffer_size", "Recording buffer size (frames)")
record_buffer_drops = Counter("record_buffer_drops", "Recording buffer drops")


_server_started = False


def start_metrics_http_server(port: int = 8000):
    """Start the prometheus client HTTP server on the given port (no-op if already started)."""
    global _server_started
    if _server_started:
        return
    try:
        start_http_server(int(port))
        _server_started = True
    except Exception:
        # best-effort; services should continue even if metrics server fails to bind
        _server_started = False


def register_flask_metrics(app):
    """Register a /metrics route on a Flask app that exposes prometheus metrics."""
    @app.route("/metrics")
    def _metrics():
        data = generate_latest(REGISTRY)
        return Response(data, mimetype=CONTENT_TYPE_LATEST)
