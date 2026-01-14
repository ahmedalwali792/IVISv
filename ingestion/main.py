# FILE: ingestion/main.py
# ------------------------------------------------------------------------------
import sys
import os
import time

from ivis_logging import setup_logging

logger = setup_logging("ingestion")
import ivis_metrics
import ivis_tracing
from ivis.common.time_utils import latency_ms, wall_clock_ms, monotonic_ms

from ingestion.capture.decoder import Decoder
from ingestion.capture.frozen import FrozenStreamDetector
from ingestion.capture.reader import Reader
from ingestion.capture.reconnect import ReconnectController
from ingestion.capture.rtsp_client import RTSPClient
from ingestion.config import Config
from ingestion.errors.fatal import ConfigError, FatalError
from ingestion.frame.anchor import Anchor
from ingestion.frame.id import FrameIdentity
from ingestion.frame.normalizer import Normalizer
from ingestion.feedback.lag_controller import LagBasedRateController
from ingestion.frame.roi import apply_mask, build_mask, parse_boxes, parse_polygons
from ingestion.frame.selector import Selector
from ingestion.heartbeat import Heartbeat
from ingestion.memory.writer import Writer
from ingestion.metrics.counters import Metrics
from ingestion.recording.buffer import RecordingBuffer
from ingestion.runtime import Runtime
from ingestion.feedback.adaptive import AdaptiveRateController

from ingestion.memory.shm_backend import ShmRingBackend

try:
    from ingestion.ipc import get_publisher
    IPC_AVAILABLE = True
except ImportError:
    IPC_AVAILABLE = False

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
        ivis_metrics.service_errors_total.labels(service="ingestion", reason=reason).inc()
    except Exception as metric_exc:
        _log_once(f"{reason}_metric", "Failed to record service error metric", metric_exc)


def _safe_metric(reason: str, fn) -> None:
    try:
        fn()
    except Exception as exc:
        _record_issue(reason, "Metrics update failed", exc)

def main():
    logger.info(">>> Ingestion Service: Initializing (Frozen v1.0) <<<")
    
    try:
        conf = Config()
    except ConfigError as e:
        logger.error("FATAL: Config Error - %s", getattr(e, 'message', str(e)))
        sys.exit(1)
    logger.info("Config summary: %s", conf.summary())

    runtime = Runtime()
    metrics = Metrics()
    # initialize tracing (best-effort)
    try:
        ivis_tracing.init_tracer(service_name=os.getenv("OTEL_SERVICE_NAME", "ingestion"))
    except Exception as exc:
        _record_issue("tracing_init_failed", "Tracing init failed", exc)
    # Start prometheus metrics server for ingestion
    try:
        port = int(os.getenv("INGESTION_METRICS_PORT", "8001"))
        ivis_metrics.start_metrics_http_server(port)
        logger.info("Prometheus metrics HTTP server started on port %s", port)
    except Exception as exc:
        _record_issue("metrics_server_failed", "Failed to start metrics server", exc)
    
    try:
        rtsp = RTSPClient(conf.rtsp_url)
        reader = Reader(rtsp)
        decoder = Decoder()
        selector = Selector(conf.target_fps, mode=conf.selector_mode)
        normalizer = Normalizer(conf.resolution, frame_color=conf.frame_color)
        anchor = Anchor()

        roi_boxes = parse_boxes(conf.roi_boxes)
        roi_polygons = parse_polygons(conf.roi_polygons)
        roi_mask = build_mask(conf.frame_width, conf.frame_height, roi_boxes, roi_polygons)
        roi_meta = None
        if roi_mask is not None:
            roi_meta = {}
            if roi_boxes:
                roi_meta["boxes"] = roi_boxes
            if roi_polygons:
                roi_meta["polygons"] = roi_polygons
            logger.info("ROI enabled (boxes=%s, polygons=%s).", len(roi_boxes), len(roi_polygons))
        
        # --- Backend Selection (Strict) ---
        if conf.memory_backend == "shm":
            slot_size = conf.frame_width * conf.frame_height * 3
            slot_count = max(1, conf.shm_buffer_bytes // slot_size)
            logger.info(
                "[Topology] Using Shared Memory Ring (slots=%s, size=%s)",
                slot_count,
                slot_size,
            )
            backend_impl = ShmRingBackend(conf.shm_name, conf.shm_meta_name, slot_size, slot_count)
        else:
            raise FatalError(f"Unsupported MEMORY_BACKEND for Stage 3: {conf.memory_backend}")

        writer = Writer(backend_impl)
        
        # --- Publisher Selection ---
        if IPC_AVAILABLE:
            logger.info("[Topology] Using Publisher transport: %s", conf.bus_transport)
            publisher = get_publisher(conf)
        else:
            raise FatalError("IPC modules missing, cannot start Publisher")

        if conf.adaptive_fps:
            controller = AdaptiveRateController(
                selector,
                conf.adaptive_min_fps,
                conf.adaptive_max_fps,
                conf.adaptive_safety,
            )
            controller.start(conf.redis_url, conf.redis_mode, conf.redis_results_channel)
            logger.info(
                "Adaptive FPS enabled (mode=%s, channel=%s).",
                conf.redis_mode,
                conf.redis_results_channel,
            )

        lag_controller = None
        if conf.adaptive_fps and conf.adaptive_lag_threshold > 0:
            lag_controller = LagBasedRateController(
                selector,
                conf.adaptive_min_fps,
                conf.adaptive_max_fps,
                conf.adaptive_lag_threshold,
                conf.adaptive_lag_hysteresis,
            )
            logger.info("Adaptive lag policy enabled (threshold=%s).", conf.adaptive_lag_threshold)

        heartbeat = Heartbeat(
            conf.stream_id,
            conf.camera_id,
            conf.redis_url,
            conf.health_stream,
            conf.health_interval_sec,
        )

        reconnect = ReconnectController(
            conf.rtsp_reconnect_min_sec,
            conf.rtsp_reconnect_max_sec,
            conf.rtsp_reconnect_factor,
            conf.rtsp_reconnect_jitter,
            conf.rtsp_max_retries,
        )
        frozen = FrozenStreamDetector(
            conf.rtsp_frozen_timeout_sec,
            conf.rtsp_frozen_hash_count,
            conf.rtsp_frozen_pts_count,
            conf.rtsp_frozen_timestamp_count,
        )

        record_buffer = None
        record_buffer_drops = 0
        if conf.record_buffer_seconds and conf.record_buffer_seconds > 0:
            max_frames = conf.record_buffer_max_frames
            if max_frames is None:
                max_frames = max(1, int(conf.record_buffer_seconds * conf.adaptive_max_fps * 1.2))
            record_buffer = RecordingBuffer(
                conf.record_buffer_seconds,
                max_frames,
                conf.record_jpeg_quality,
            )
            logger.info("Recording buffer enabled (seconds=%s, max_frames=%s).", conf.record_buffer_seconds, max_frames)
        
        rtsp.connect()

    except FatalError as e:
        logger.error("FATAL: Startup Failed - %s", e.message)
        sys.exit(1)

    logger.info(f">>> Ingestion Running | Stream: {conf.stream_id} <<<")

    def _attempt_reconnect(reason: str) -> bool:
        _record_issue(f"rtsp_{reason}", "RTSP reconnect triggered", None)
        heartbeat.tick(status="degraded", reason=reason)
        while runtime.should_continue():
            delay = reconnect.wait()
            if delay is None:
                return False
            logger.warning(
                "Attempting reconnect in %.2fs (reason=%s, attempt=%s).",
                delay,
                reason,
                reconnect.attempts,
            )
            if rtsp.reconnect():
                reconnect.reset()
                frozen.reset()
                logger.info("Source reconnected (reason=%s).", reason)
                heartbeat.tick(status="ok", reason="reconnected")
                return True
        return False

    while runtime.should_continue():
        try:
            heartbeat.tick()

            packet = reader.next_packet()

            if packet is None:
                if conf.video_loop and rtsp.is_file:
                    logger.warning("Source EOF reached. Rewinding file input.")
                    rtsp.rewind()
                    # avoid tight rewind loop when VideoCapture doesn't
                    # return frames immediately after seeking
                    time.sleep(0.05)
                    continue
                if rtsp.is_file:
                    raise FatalError("Source EOF or Connection Lost")
                freeze_reason = frozen.check(monotonic_ms())
                if freeze_reason:
                    if not _attempt_reconnect(f"frozen_{freeze_reason}"):
                        raise FatalError("Source reconnect failed")
                else:
                    time.sleep(0.05)
                continue

            reconnect.reset()

            if packet.pts <= 0:
                metrics.inc_dropped_pts()
                continue

            try:
                raw_frame = decoder.decode(packet)
                # capture span: decoding/capture
                try:
                    with ivis_tracing.start_span("ingestion.capture", {"stream_id": conf.stream_id}):
                        pass
                except Exception as exc:
                    _record_issue("tracing_span_capture_failed", "Tracing span failed (capture)", exc)
            except Exception as exc:
                metrics.inc_dropped_corrupt()
                logger.debug("Decode error: %s", exc)
                continue
            if raw_frame is None:
                metrics.inc_dropped_corrupt()
                continue
            
            metrics.inc_captured()
            _safe_metric("metrics_frames_in_failed", ivis_metrics.frames_in_total.inc)

            if not selector.allow(packet.pts):
                metrics.inc_dropped_fps()
                continue

            clean_frame = normalizer.process(raw_frame)
            if roi_mask is not None:
                clean_frame = apply_mask(clean_frame, roi_mask)
            # normalization span
            try:
                with ivis_tracing.start_span("ingestion.normalize", {"stream_id": conf.stream_id}):
                    pass
            except Exception as exc:
                _record_issue("tracing_span_normalize_failed", "Tracing span failed (normalize)", exc)
            fingerprint = anchor.generate(clean_frame)
            frozen.note_frame(packet.pts, packet.timestamp_ms, fingerprint, packet.mono_ms)
            freeze_reason = frozen.check(packet.mono_ms)
            if freeze_reason and not rtsp.is_file:
                if not _attempt_reconnect(f"frozen_{freeze_reason}"):
                    raise FatalError("Source reconnect failed")
                continue
            identity = FrameIdentity(conf.stream_id, packet.pts, fingerprint)
            if record_buffer is not None:
                if record_buffer.add_frame(clean_frame, packet.timestamp_ms):
                    _safe_metric("record_buffer_size_failed", lambda: ivis_metrics.record_buffer_size.set(record_buffer.size()))
                    if record_buffer.drops > record_buffer_drops:
                        _safe_metric(
                            "record_buffer_drops_failed",
                            lambda: ivis_metrics.record_buffer_drops.inc(record_buffer.drops - record_buffer_drops),
                        )
                        record_buffer_drops = record_buffer.drops
            # Write to SHM
            try:
                # SHM write span
                ref = None
                try:
                    with ivis_tracing.start_span("ingestion.shm_write", {"frame_id": identity.frame_id, "stream_id": identity.stream_id}):
                        ref = writer.write(clean_frame, identity)
                except Exception as exc:
                    _record_issue("tracing_span_shm_write_failed", "Tracing span failed (shm_write)", exc)
                    # fallback to direct write if tracing wrapper failed
                    ref = writer.write(clean_frame, identity)
            except Exception:
                ref = None

            # publish span
            try:
                with ivis_tracing.start_span("ingestion.publish", {"frame_id": identity.frame_id, "stream_id": identity.stream_id}):
                    published = publisher.publish(identity, packet.timestamp_ms, packet.mono_ms, ref, roi_meta=roi_meta)
            except Exception as exc:
                _record_issue("tracing_span_publish_failed", "Tracing span failed (publish)", exc)
                # if tracing wrapper fails, attempt publish anyway
                published = publisher.publish(identity, packet.timestamp_ms, packet.mono_ms, ref, roi_meta=roi_meta)
            if not published:
                # Frame dropped due to backpressure/lag
                metrics.inc_dropped_reason("lag")
                _safe_metric("metrics_frames_dropped_failed", lambda: ivis_metrics.frames_dropped_total.labels(reason="lag").inc())
                _safe_metric("metrics_drops_total_failed", lambda: ivis_metrics.drops_total.labels(reason="lag").inc())
                logger.debug("Dropped frame due to backpressure/lag (stream length exceeded)")
            else:
                metrics.inc_processed()
                _safe_metric("metrics_frames_out_failed", ivis_metrics.frames_out_total.inc)
            # end-to-end: best-effort observe latency from capture timestamp to now
            try:
                if packet.timestamp_ms:
                    now_ms = wall_clock_ms()
                    end_ms = latency_ms(now_ms, int(packet.timestamp_ms))
                    _safe_metric("metrics_end_to_end_latency_failed", lambda: ivis_metrics.end_to_end_latency_ms.observe(end_ms))
            except Exception as exc:
                _record_issue("end_to_end_latency_failed", "End-to-end latency calculation failed", exc)
            # Update last-observed redis stream lag metric (best-effort)
            try:
                if hasattr(publisher, "redis"):
                    xlen = int(publisher.redis.xlen(publisher.stream) or 0)
                    metrics.set_redis_stream_lag(xlen)
                    _safe_metric("metrics_redis_lag_failed", lambda: ivis_metrics.redis_lag.set(xlen))
                    if lag_controller is not None:
                        if lag_controller.update(xlen):
                            logger.info("Adaptive FPS lag cap updated (target_fps=%s).", selector.target_fps)
            except Exception as exc:
                _record_issue("redis_lag_query_failed", "Failed to read Redis stream length", exc)
            _safe_metric("metrics_adaptive_fps_failed", lambda: ivis_metrics.adaptive_fps_current.set(selector.target_fps))
        
        except FatalError as e:
            logger.error("!!! FATAL ERROR !!! %s | Context: %s", getattr(e, 'message', str(e)), getattr(e, 'context', None))
            break

        except Exception as e:
            logger.exception("!!! UNHANDLED CRASH !!! %s", str(e))
            break

    rtsp.close()
    runtime.shutdown()
    sys.exit(1)

if __name__ == "__main__":
    main()
