# FILE: ingestion/main.py
# ------------------------------------------------------------------------------
import sys
import os
import time

from ivis_logging import setup_logging

logger = setup_logging("ingestion")
import ivis_metrics
import ivis_tracing
from ivis.common.time_utils import latency_ms, wall_clock_ms

from ingestion.capture.decoder import Decoder
from ingestion.capture.reader import Reader
from ingestion.capture.rtsp_client import RTSPClient
from ingestion.config import Config
from ingestion.errors.fatal import ConfigError, FatalError
from ingestion.frame.anchor import Anchor
from ingestion.frame.id import FrameIdentity
from ingestion.frame.normalizer import Normalizer
from ingestion.frame.selector import Selector
from ingestion.heartbeat import Heartbeat
from ingestion.memory.writer import Writer
from ingestion.metrics.counters import Metrics
from ingestion.runtime import Runtime
from ingestion.feedback.adaptive import AdaptiveRateController

from ingestion.memory.shm_backend import ShmRingBackend

try:
    from ingestion.ipc import get_publisher
    IPC_AVAILABLE = True
except ImportError:
    IPC_AVAILABLE = False

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
    except Exception:
        pass
    # Start prometheus metrics server for ingestion
    try:
        port = int(os.getenv("INGESTION_METRICS_PORT", "8001"))
        ivis_metrics.start_metrics_http_server(port)
        logger.info("Prometheus metrics HTTP server started on port %s", port)
    except Exception:
        logger.exception("Failed to start metrics server")
    
    try:
        rtsp = RTSPClient(conf.rtsp_url)
        reader = Reader(rtsp)
        decoder = Decoder()
        selector = Selector(conf.target_fps, mode=conf.selector_mode)
        normalizer = Normalizer(conf.resolution, frame_color=conf.frame_color)
        anchor = Anchor()
        
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

        heartbeat = Heartbeat(conf.stream_id)
        
        rtsp.connect()

    except FatalError as e:
        logger.error("FATAL: Startup Failed - %s", e.message)
        sys.exit(1)

    logger.info(f">>> Ingestion Running | Stream: {conf.stream_id} <<<")

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
                if conf.rtsp_max_retries > 0:
                    logger.warning(
                        "Source read failed. Attempting reconnect (max_retries=%s, backoff=%ss).",
                        conf.rtsp_max_retries,
                        conf.rtsp_retry_backoff_sec,
                    )
                    reconnected = False
                    for attempt in range(1, conf.rtsp_max_retries + 1):
                        time.sleep(conf.rtsp_retry_backoff_sec * attempt)
                        if rtsp.reconnect():
                            reconnected = True
                            logger.info("Source reconnected after attempt %s.", attempt)
                            break
                    if reconnected:
                        continue
                    raise FatalError("Source reconnect failed")
                raise FatalError("Source EOF or Connection Lost")

            if packet.pts <= 0:
                metrics.inc_dropped_pts()
                continue

            try:
                raw_frame = decoder.decode(packet)
                # capture span: decoding/capture
                try:
                    with ivis_tracing.start_span("ingestion.capture", {"stream_id": conf.stream_id}):
                        pass
                except Exception:
                    pass
            except Exception as exc:
                metrics.inc_dropped_corrupt()
                logger.debug("Decode error: %s", exc)
                continue
            if raw_frame is None:
                metrics.inc_dropped_corrupt()
                continue
            
            metrics.inc_captured()
            try:
                ivis_metrics.frames_in_total.inc()
            except Exception:
                pass

            if not selector.allow(packet.pts):
                metrics.inc_dropped_fps()
                continue

            clean_frame = normalizer.process(raw_frame)
            # normalization span
            try:
                with ivis_tracing.start_span("ingestion.normalize", {"stream_id": conf.stream_id}):
                    pass
            except Exception:
                pass
            fingerprint = anchor.generate(clean_frame)
            identity = FrameIdentity(conf.stream_id, packet.pts, fingerprint)
            # Measure SHM write latency
            try:
                sw_start = time.time()
                # SHM write span
                ref = None
                try:
                    with ivis_tracing.start_span("ingestion.shm_write", {"frame_id": identity.frame_id, "stream_id": identity.stream_id}):
                        ref = writer.write(clean_frame, identity)
                except Exception:
                    # fallback to direct write if tracing wrapper failed
                    ref = writer.write(clean_frame, identity)
                sw_ms = (time.time() - sw_start) * 1000.0
                try:
                    ivis_metrics.shm_write_latency_ms.observe(sw_ms)
                except Exception:
                    pass
            except Exception:
                ref = None

            # publish span
            try:
                with ivis_tracing.start_span("ingestion.publish", {"frame_id": identity.frame_id, "stream_id": identity.stream_id}):
                    published = publisher.publish(identity, packet.timestamp_ms, packet.mono_ms, ref)
            except Exception:
                # if tracing wrapper fails, attempt publish anyway
                published = publisher.publish(identity, packet.timestamp_ms, packet.mono_ms, ref)
            if not published:
                # Frame dropped due to backpressure/lag
                metrics.inc_dropped_reason("lag")
                try:
                    ivis_metrics.frames_dropped_total.labels(reason="lag").inc()
                except Exception:
                    pass
                logger.debug("Dropped frame due to backpressure/lag (stream length exceeded)")
            else:
                metrics.inc_processed()
                try:
                    ivis_metrics.frames_out_total.inc()
                except Exception:
                    pass
            # end-to-end: best-effort observe latency from capture timestamp to now
            try:
                if packet.timestamp_ms:
                    now_ms = wall_clock_ms()
                    end_ms = latency_ms(now_ms, int(packet.timestamp_ms))
                    ivis_metrics.end_to_end_latency_ms.observe(end_ms)
            except Exception:
                pass
            # Update last-observed redis stream lag metric (best-effort)
            try:
                if hasattr(publisher, "redis"):
                    xlen = int(publisher.redis.xlen(publisher.stream) or 0)
                    metrics.set_redis_stream_lag(xlen)
                    try:
                        ivis_metrics.redis_lag.set(xlen)
                    except Exception:
                        pass
            except Exception:
                pass
        
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
