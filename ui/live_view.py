# FILE: ui/live_view.py
# ------------------------------------------------------------------------------
import json
import os
import threading
import time

import cv2
import numpy as np
from flask import Flask, Response, render_template_string

from ivis.common.config.base import redact_config
from ivis_logging import setup_logging
from memory.shm_ring import ShmRing
from ivis.common.contracts.validators import validate_frame_contract_v1, ContractValidationError
from ivis.common.contracts.result_contract import validate_result_contract_v1
from detection.metrics.counters import metrics as detection_metrics
from ui.results_cache import ResultsCache
import ivis_metrics
import ivis_tracing


ZMQ_SUB_ENDPOINT = os.getenv("ZMQ_SUB_ENDPOINT", "tcp://localhost:5555")
ZMQ_RESULTS_SUB_ENDPOINT = os.getenv("ZMQ_RESULTS_SUB_ENDPOINT", "tcp://localhost:5557")

SHM_NAME = os.getenv("SHM_NAME", "ivis_shm_data")
SHM_META_NAME = os.getenv("SHM_META_NAME", "ivis_shm_meta")
SHM_BUFFER_BYTES = int(os.getenv("SHM_BUFFER_BYTES", "50000000"))
SHM_CACHE_SECONDS = float(os.getenv("SHM_CACHE_SECONDS", "0"))
SHM_CACHE_FPS = float(os.getenv("SHM_CACHE_FPS", "0"))

FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", "640"))
FRAME_HEIGHT = int(os.getenv("FRAME_HEIGHT", "480"))
# FRAME_COLOR_SPACE is fixed to 'bgr' for v1 contract; downstream code
# should assume frames are in this colorspace and avoid conversions.
FRAME_COLOR_SPACE = os.getenv("FRAME_COLOR_SPACE", "bgr").lower()

app = Flask(__name__)
logger = setup_logging("ui")

_warned = set()


def _log_once(key: str, message: str, exc: Exception = None) -> None:
    if key in _warned:
        return
    _warned.add(key)
    if exc is not None:
        logger.warning("%s: %s", message, exc)
    else:
        logger.warning("%s", message)


def _record_issue(reason: str, message: str, exc: Exception = None) -> None:
    _log_once(reason, message, exc)
    try:
        ivis_metrics.service_errors_total.labels(service="ui", reason=reason).inc()
    except Exception as metric_exc:
        _log_once(f"{reason}_metric", "Failed to record service error metric", metric_exc)


def _safe_metric(reason: str, fn) -> None:
    try:
        fn()
    except Exception as exc:
        _record_issue(reason, "Metrics update failed", exc)

RESULTS_CACHE_MAX = int(os.getenv("UI_RESULTS_CACHE_MAX", "2000"))
RESULTS_CACHE_TTL_SEC = float(os.getenv("UI_RESULTS_CACHE_TTL_SEC", "60"))

latest_lock = threading.Lock()
latest_frame = None
latest_meta = {}
results_cache = ResultsCache(max_entries=RESULTS_CACHE_MAX, ttl_seconds=RESULTS_CACHE_TTL_SEC)
results_cache_lock = threading.Lock()
shm_ring = None
last_shm_error = None
active_shm_name = None
last_frame_ts = 0.0
fps_ema = 0.0
last_contract_ts = 0.0
last_result = {}
last_shm_ts = 0.0
_threads_started = False
_threads_lock = threading.Lock()

def _update_cache_metric():
    _safe_metric("metrics_ui_cache_size_failed", lambda: ivis_metrics.ui_results_cache_size.set(len(results_cache)))


def _cache_set(frame_id: str, result: dict):
    with results_cache_lock:
        results_cache.put(frame_id, result)
        _update_cache_metric()


def _cache_get(frame_id: str):
    with results_cache_lock:
        result = results_cache.get(frame_id)
        _update_cache_metric()
        return result


def _start_background_threads():
    global _threads_started
    with _threads_lock:
        if _threads_started:
            return
        threading.Thread(target=_frame_loop, daemon=True).start()
        threading.Thread(target=_results_loop, daemon=True).start()
        threading.Thread(target=_shm_fallback_loop, daemon=True).start()
        _threads_started = True
        logger.info("Background threads started.")


def _get_ring():
    global shm_ring, last_shm_error, active_shm_name
    if shm_ring is None:
        slot_size = FRAME_WIDTH * FRAME_HEIGHT * 3
        if SHM_CACHE_SECONDS > 0 and SHM_CACHE_FPS > 0:
            slot_count = max(1, int(SHM_CACHE_SECONDS * SHM_CACHE_FPS))
        else:
            slot_count = max(1, SHM_BUFFER_BYTES // slot_size)
        candidates = [
            (SHM_NAME, SHM_META_NAME),
            (f"ivis_shm_data_{slot_size}_{slot_count}", f"ivis_shm_meta_{slot_size}_{slot_count}"),
            ("ivis_shm_data", "ivis_shm_meta"),
        ]
        last_error = None
        for data_name, meta_name in candidates:
            try:
                shm_ring = ShmRing(data_name, meta_name, slot_size, slot_count, create=False)
                active_shm_name = data_name
                last_shm_error = None
                break
            except Exception as exc:
                last_error = exc
                shm_ring = None
        if shm_ring is None and last_error is not None:
            last_shm_error = str(last_error)
    return shm_ring


def _overlay(frame_bgr: np.ndarray, result: dict, fps_value: float) -> np.ndarray:
    if not result.get("detections") and not result.get("tracks"):
         logger.debug("Overlay: No detections/tracks in result for overlay")
    timing = result.get("timing", {})
    inference_ms = timing.get("inference_ms")
    model_ms = timing.get("model_ms")
    track_ms = timing.get("track_ms")
    # Expect ResultContractV1: detections is a list of dicts
    detections = result.get("detections", []) if isinstance(result.get("detections", []), list) else []
    # Tracks derived from detections that include a track_id
    tracks = [{"bbox": d.get("bbox"), "track_id": d.get("track_id")} for d in detections if d.get("track_id") is not None]
    info_lines = [f"FPS: {fps_value:.1f}", f"DET: {len(detections)} | TRK: {len(tracks)}"]
    if inference_ms is not None:
        info_lines.append(f"INF: {inference_ms:.1f} ms")
    if model_ms is not None and track_ms is not None:
        info_lines.append(f"DET: {model_ms:.1f} ms | TRK: {track_ms:.1f} ms")
    y = 20
    for line in info_lines:
        cv2.putText(
            frame_bgr,
            line,
            (10, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
        y += 22
    for det in detections:
        try:
            bbox = det.get("bbox")
            conf = float(det.get("conf", 0.0))
            cls_id = det.get("class_id")
            if not bbox or len(bbox) != 4:
                continue
            x1, y1, x2, y2 = map(int, map(round, bbox))
        except Exception:
            continue
        color = (0, 200, 255)
        cv2.rectangle(frame_bgr, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
        label = f"C{int(cls_id)} {conf:.2f}" if cls_id is not None else f"{conf:.2f}"
        if det.get("class_name"):
            label = f"{det.get('class_name')} {conf:.2f}"
        cv2.putText(
            frame_bgr,
            label,
            (int(x1), max(0, int(y1) - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
            cv2.LINE_AA,
        )

    frame_h, frame_w = frame_bgr.shape[:2]
    for track in tracks:
        bbox = track.get("bbox", [0, 0, 0, 0])
        if len(bbox) != 4:
            continue
        x1, y1, x2, y2 = bbox
        # Accept either [x1, y1, x2, y2] or [x, y, w, h].
        if x2 > x1 and y2 > y1 and x2 <= frame_w and y2 <= frame_h:
            x, y, w, h = x1, y1, x2 - x1, y2 - y1
        else:
            x, y, w, h = x1, y1, x2, y2
        track_id = track.get("track_id", -1)
        color = (0, 255, 0)
        cv2.rectangle(frame_bgr, (int(x), int(y)), (int(x + w), int(y + h)), color, 2)
        cv2.putText(
            frame_bgr,
            f"ID {track_id}",
            (int(x), max(0, int(y) - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
            cv2.LINE_AA,
        )
    return frame_bgr


def _frame_loop():
    try:
        import zmq
    except Exception as exc:
        raise RuntimeError(f"Missing ZeroMQ dependency: {exc}") from exc

    ctx = zmq.Context.instance()
    socket = ctx.socket(zmq.SUB)
    socket.connect(ZMQ_SUB_ENDPOINT)
    socket.setsockopt(zmq.SUBSCRIBE, b"")
    while True:
        try:
            payload = socket.recv()
            contract = json.loads(payload.decode("utf-8"))
            logger.debug("Received contract via ZMQ: %s", contract.get("frame_id"))
            try:
                with ivis_tracing.start_span("ui.consume", {"frame_id": contract.get("frame_id"), "stream_id": contract.get("stream_id")}):
                    _handle_contract(contract)
            except Exception:
                _handle_contract(contract)
        except Exception as exc:
            _record_issue("ui_frame_loop_failed", "Frame loop error", exc)
            time.sleep(0.1)


def _results_loop():
    try:
        import zmq
    except Exception as exc:
        raise RuntimeError(f"Missing ZeroMQ dependency: {exc}") from exc

    global last_result
    ctx = zmq.Context.instance()
    socket = ctx.socket(zmq.SUB)
    socket.connect(ZMQ_RESULTS_SUB_ENDPOINT)
    socket.setsockopt(zmq.SUBSCRIBE, b"")
    while True:
        try:
            payload = socket.recv()
            result = json.loads(payload.decode("utf-8"))
            try:
                validate_result_contract_v1(result)
            except ContractValidationError as exc:
                detection_metrics.inc_dropped_reason(getattr(exc, "reason_code", "result_validation_failed"))
                logger.debug("Dropped result from ZMQ: %s", getattr(exc, "message", str(exc)))
                continue
            frame_id = result.get("frame_id")
            if frame_id:
                _cache_set(frame_id, result)
                last_result = result
                logger.debug("DEBUG: Cached result for frame %s (ts=%s)", frame_id, result.get("timestamp_ms"))
        except Exception as exc:
            _record_issue("ui_results_loop_failed", "Results loop error", exc)
            time.sleep(0.1)
            



def _handle_contract(contract: dict):
    global last_contract_ts, last_shm_ts
    mem = contract.get("memory", {})
    key = mem.get("key")
    gen = mem.get("generation", 0)
    if not key:
        return
    # Strict validation: fail-fast and drop invalid contracts
    try:
        validate_frame_contract_v1(contract)
    except ContractValidationError as exc:
        try:
            detection_metrics.inc_dropped_reason(getattr(exc, "reason_code", "validation_failed"))
        except Exception as metric_exc:
            _record_issue("ui_dropped_reason_failed", "Failed to update dropped reason metric", metric_exc)
        logger.debug("Dropped contract in UI due to validation: %s", getattr(exc, "message", str(exc)))
        return
    try:
        slot = int(key)
    except ValueError:
        return
    try:
        ring = _get_ring()
        # measure SHM read latency
        rr_start = time.time()
        # trace SHM read in UI
        try:
            with ivis_tracing.start_span("ui.shm_read", {"frame_id": contract.get("frame_id"), "stream_id": contract.get("stream_id")}):
                data = ring.read(slot, gen)
        except Exception as exc:
            _record_issue("tracing_span_shm_read_failed", "Tracing span failed (ui shm_read)", exc)
            data = ring.read(slot, gen)
        rr_ms = (time.time() - rr_start) * 1000.0
        _safe_metric("metrics_shm_read_latency_failed", lambda: ivis_metrics.shm_read_latency_ms.observe(rr_ms))
        if not data:
            return
    except Exception:
        logger.exception("Error reading from SHM ring for slot=%s gen=%s", slot, gen)
        return
    logger.debug("SHM read returned %s bytes for slot=%s gen=%s", None if data is None else len(data), slot, gen)
    arr = np.frombuffer(data, dtype=np.uint8)
    arr = arr.reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))
    # Make a writable copy - buffers from shared memory are readonly in NumPy
    # Ingestion ensures the frame is in FRAME_COLOR_SPACE (bgr v1); no downstream conversion.
    frame_bgr = arr.copy()
    # ensure contiguous writable image for OpenCV
    frame_bgr = np.ascontiguousarray(frame_bgr, dtype=np.uint8)
    frame_id = contract.get("frame_id")
    # Prefer the exact ResultContractV1 for this frame_id; fall back to last_result only
    # if it's recent to avoid drawing stale tracks for long periods.
    result = _cache_get(frame_id)
    if result is None:
        # Use last_result only when it was updated within 0.5s
        if time.perf_counter() - last_shm_ts < float(os.getenv("MAX_RESULT_AGE_SEC", "0.5")):
            result = last_result
        else:
            result = {"detections": [], "tracks": [], "timing": {}}
    else:
        # Ensure result is recent relative to this frame's timestamp
        try:
            res_ts = int(result.get("timestamp_ms", 0))
            frame_ts = int(contract.get("timestamp_ms", 0))
            max_age_ms = int(os.getenv("MAX_RESULT_AGE_MS", "500"))
            if abs(res_ts - frame_ts) > max_age_ms:
                detection_metrics.inc_dropped_reason("result_lag")
                logger.debug("Dropping result for frame %s due to result lag (res_ts=%s frame_ts=%s)", frame_id, res_ts, frame_ts)
                result = {"detections": [], "tracks": [], "timing": {}}
        except Exception:
            # If timestamps malformed, drop the result
            detection_metrics.inc_dropped_reason("result_malformed_timestamp")
            result = {"detections": [], "tracks": [], "timing": {}}
    global last_frame_ts, fps_ema
    now = time.perf_counter()
    if last_frame_ts > 0:
        fps = 1.0 / max(1e-6, (now - last_frame_ts))
        fps_ema = fps if fps_ema == 0.0 else (0.9 * fps_ema + 0.1 * fps)
    last_frame_ts = now
    _safe_metric("metrics_fps_out_failed", lambda: ivis_metrics.fps_out.set(fps_ema))
    # overlay span (drawing + composite)
    try:
        with ivis_tracing.start_span("ui.overlay", {"frame_id": frame_id, "stream_id": contract.get("stream_id")}):
            frame_bgr = _overlay(frame_bgr, result, fps_ema)
    except Exception as exc:
        _record_issue("tracing_span_overlay_failed", "Tracing span failed (ui overlay)", exc)
        frame_bgr = _overlay(frame_bgr, result, fps_ema)
    with latest_lock:
        global latest_frame, latest_meta
        latest_frame = frame_bgr
        latest_meta = contract
        last_contract_ts = time.perf_counter()
        last_shm_ts = time.perf_counter()


def _shm_fallback_loop():
    while True:
        try:
            now = time.perf_counter()
            if now - last_contract_ts < 0.5:
                time.sleep(0.1)
                continue
            # globals used/updated in this loop
            global last_frame_ts, fps_ema, latest_frame, latest_meta, last_shm_ts
            ring = _get_ring()
            if ring is None:
                time.sleep(0.1)
                continue
            data, _, _ = ring.read_latest()
            if not data:
                time.sleep(0.1)
                continue
            logger.debug("SHM fallback read %s bytes", len(data))
            arr = np.frombuffer(data, dtype=np.uint8)
            arr = arr.reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))
            # Make writable copy for OpenCV drawing
            frame_bgr = arr.copy()
            # Ingestion guarantees FRAME_COLOR_SPACE == bgr; no color conversion required.
            frame_bgr = np.ascontiguousarray(frame_bgr, dtype=np.uint8)
            # (globals declared above)
            now = time.perf_counter()
            if last_frame_ts > 0:
                fps = 1.0 / max(1e-6, (now - last_frame_ts))
                fps_ema = fps if fps_ema == 0.0 else (0.9 * fps_ema + 0.1 * fps)
            last_frame_ts = now
            frame_bgr = _overlay(frame_bgr, last_result if (time.perf_counter() - last_shm_ts) < 0.5 else {"detections": [], "tracks": [], "timing": {}}, fps_ema)
            with latest_lock:
                latest_frame = frame_bgr
                latest_meta = {
                    "stream_id": os.getenv("STREAM_ID"),
                    "camera_id": os.getenv("CAMERA_ID"),
                }
                last_shm_ts = time.perf_counter()
        except Exception as exc:
            _record_issue("ui_shm_fallback_failed", "SHM fallback loop error", exc)
            time.sleep(0.1)


@app.route("/")
def index():
    _start_background_threads()
    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <title>IVIS Live View</title>
      <style>
        body { font-family: Arial, sans-serif; background: #111; color: #eee; text-align: center; }
        .wrap { max-width: 960px; margin: 20px auto; }
        img { width: 100%; border: 1px solid #333; }
        .meta { margin-top: 8px; font-size: 14px; color: #aaa; }
        .note { margin-top: 6px; font-size: 12px; color: #777; }
      </style>
    </head>
    <body>
      <div class="wrap">
        <h2>IVIS Live View</h2>
        <img src="/stream" />
        <div class="meta">Overlay shows FPS and inference time</div>
        <div class="note">Metrics: /metrics</div>
      </div>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/stream")
def stream():
    _start_background_threads()
    def gen():
        while True:
            with latest_lock:
                frame = None if latest_frame is None else latest_frame.copy()
            if frame is None:
                try:
                    ring = _get_ring()
                    data, _, _ = ring.read_latest()
                    if data:
                        arr = np.frombuffer(data, dtype=np.uint8)
                        arr = arr.reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))
                        frame_bgr = arr.copy()
                        frame_bgr = np.ascontiguousarray(frame_bgr, dtype=np.uint8)
                        frame = _overlay(frame_bgr, last_result, fps_ema)
                        logger.debug("Stream generated frame from SHM latest")
                except Exception:
                    logger.exception("Error generating frame from SHM in stream()")
                    frame = None
            if frame is None:
                time.sleep(0.05)
                continue
            ok, jpeg = cv2.imencode(".jpg", frame)
            if not ok:
                continue
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/health")
def health():
    _start_background_threads()
    return {"status": "ok"}


@app.route("/json_metrics")
def json_metrics():
    _start_background_threads()
    with latest_lock:
        meta = dict(latest_meta) if latest_meta else {}
    return {
        "fps": fps_ema,
        "last_frame_id": meta.get("frame_id"),
        "stream_id": meta.get("stream_id"),
        "camera_id": meta.get("camera_id"),
        "last_contract_age_ms": int((time.perf_counter() - last_contract_ts) * 1000) if last_contract_ts else None,
        "last_shm_age_ms": int((time.perf_counter() - last_shm_ts) * 1000) if last_shm_ts else None,
        "shm_name": active_shm_name,
        "shm_error": last_shm_error,
        "threads_started": _threads_started,
    }


def main():
    logger.info(
        "Config summary: %s",
        redact_config(
            {
                "ZMQ_SUB_ENDPOINT": ZMQ_SUB_ENDPOINT,
                "ZMQ_RESULTS_SUB_ENDPOINT": ZMQ_RESULTS_SUB_ENDPOINT,
                "SHM_NAME": SHM_NAME,
                "SHM_META_NAME": SHM_META_NAME,
                "SHM_BUFFER_BYTES": SHM_BUFFER_BYTES,
                "SHM_CACHE_SECONDS": SHM_CACHE_SECONDS,
                "SHM_CACHE_FPS": SHM_CACHE_FPS,
                "FRAME_WIDTH": FRAME_WIDTH,
                "FRAME_HEIGHT": FRAME_HEIGHT,
                "FRAME_COLOR_SPACE": FRAME_COLOR_SPACE,
            }
        ),
    )
    _start_background_threads()
    # Register Prometheus /metrics endpoint on Flask app
    try:
        ivis_metrics.register_flask_metrics(app)
    except Exception:
        logger.exception("Failed to register Prometheus metrics route")
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)


if __name__ == "__main__":
    main()
