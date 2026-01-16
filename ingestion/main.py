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
from ivis_health import ServiceState, HealthServer

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

    health_host = os.getenv("HEALTH_BIND", "127.0.0.1")
    health_port = int(os.getenv("INGESTION_HEALTH_PORT", "9001"))
    state = ServiceState("ingestion")
    HealthServer(state, host=health_host, port=health_port).start_in_thread()
    state.set_check("config_loaded", True, details={"stream_id": conf.stream_id, "camera_id": conf.camera_id})

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
            if conf.shm_cache_seconds and conf.shm_cache_seconds > 0:
                slot_count = max(1, int(conf.target_fps * conf.shm_cache_seconds))
            else:
                slot_count = max(1, conf.shm_buffer_bytes // slot_size)
            logger.info(
                "[Topology] Using Shared Memory Ring (slots=%s, size=%s)",
                slot_count,
                slot_size,
            )
            backend_impl = ShmRingBackend(conf.shm_name, conf.shm_meta_name, slot_size, slot_count)
            state.set_check(
                "shm_ready",
                True,
                details={"shm_name": conf.shm_name, "shm_meta_name": conf.shm_meta_name, "slot_size": slot_size, "slot_count": slot_count},
            )
        else:
            raise FatalError(f"Unsupported MEMORY_BACKEND for Stage 3: {conf.memory_backend}")

        writer = Writer(backend_impl)
        
        # --- Publisher Selection ---
        if IPC_AVAILABLE:
            logger.info("[Topology] Using Publisher transport: %s", conf.bus_transport)
            publisher = get_publisher(conf)
            state.set_check(
                "bus_ready",
                True,
                details={"transport": conf.bus_transport, "endpoint": getattr(conf, "zmq_pub_endpoint", None)},
            )
        else:
            raise FatalError("IPC modules missing, cannot start Publisher")

        if conf.adaptive_fps:
            controller = AdaptiveRateController(
                selector,
                conf.adaptive_min_fps,
                conf.adaptive_max_fps,
                conf.adaptive_safety,
            )
            controller.start(conf.zmq_results_sub_endpoint)
            logger.info("Adaptive FPS enabled (results endpoint=%s).", conf.zmq_results_sub_endpoint)

        heartbeat = Heartbeat(conf.stream_id, conf.camera_id, conf.health_interval_sec)

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
        state.set_check("source_ready", True, details={"rtsp_url": conf.rtsp_url})
        state.compute_ready(["config_loaded", "shm_ready", "bus_ready", "source_ready"])

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

    try:
        while runtime.should_continue():
            try:
                state.touch_loop()
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

                if ref is not None:
                    state.inc("frames_written", 1)
                    state.set_meta("last_frame_id", identity.frame_id)
                    state.set_meta("last_shm_write_ts", time.time())

                # publish span
                try:
                    with ivis_tracing.start_span("ingestion.publish", {"frame_id": identity.frame_id, "stream_id": identity.stream_id}):
                        published = publisher.publish(identity, packet.timestamp_ms, packet.mono_ms, ref, roi_meta=roi_meta)
                except Exception as exc:
                    _record_issue("tracing_span_publish_failed", "Tracing span failed (publish)", exc)
                    # if tracing wrapper fails, attempt publish anyway
                    published = publisher.publish(identity, packet.timestamp_ms, packet.mono_ms, ref, roi_meta=roi_meta)
                if not published:
                    state.set_check("bus_active", False, reason="publish_failed")
                    # Frame dropped due to backpressure/lag
                    metrics.inc_dropped_reason("lag")
                    _safe_metric("metrics_frames_dropped_failed", lambda: ivis_metrics.frames_dropped_total.labels(reason="lag").inc())
                    _safe_metric("metrics_drops_total_failed", lambda: ivis_metrics.drops_total.labels(reason="lag").inc())
                    logger.debug("Dropped frame due to backpressure/lag (stream length exceeded)")
                else:
                    state.inc("frames_published", 1)
                    state.set_check("bus_active", True)
                    state.set_meta("last_publish_ts", time.time())
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
                # No external lag source when running without a broker
                _safe_metric("metrics_adaptive_fps_failed", lambda: ivis_metrics.adaptive_fps_current.set(selector.target_fps))
        
            except FatalError as e:
                state.set_error("fatal_error", e, context=getattr(e, "context", None))
                state.set_ready(False)
                logger.error("!!! FATAL ERROR !!! %s | Context: %s", getattr(e, 'message', str(e)), getattr(e, 'context', None))
                break

            except Exception as e:
                logger.exception("!!! UNHANDLED CRASH !!! %s", str(e))
                break

    finally:
        logger.info("Cleaning up resources...")
        rtsp.close()
        try:
            if 'publisher' in locals() and hasattr(publisher, 'close'):
                publisher.close()
                logger.info("Publisher closed.")
        except Exception as e:
            logger.warning("Error closing publisher: %s", e)
        
        runtime.shutdown()
        logger.info("Ingestion Service Stopped.")
        sys.exit(0) # clean exit

if __name__ == "__main__":
    main()
