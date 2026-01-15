#!/usr/bin/env python
import sys
import os
import time

from ivis_logging import setup_logging
logger = setup_logging("detection")

import ivis_metrics
import ivis_tracing
from ivis.common.time_utils import latency_ms, wall_clock_ms
from ivis_health import ServiceState, HealthServer

from detection.config import Config
from detection.errors.fatal import FatalError, NonFatalError
from detection.frame.decoder import FrameDecoder
from detection.ingest.consumer import FrameConsumer
from detection.memory.reader import MemoryReader
from detection.model.loader import load_model
from detection.model.runner import ModelRunner
from detection.postprocess.parse import parse_output
from detection.publish.results import ResultPublisher
from detection.runtime import Runtime
from detection.metrics.counters import metrics
from ivis.common.contracts.validators import validate_frame_contract_v1, ContractValidationError


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
        ivis_metrics.service_errors_total.labels(service="detection", reason=reason).inc()
    except Exception as metric_exc:
        _log_once(f"{reason}_metric", "Failed to record service error metric", metric_exc)


def _safe_metric(reason: str, fn) -> None:
    try:
        fn()
    except Exception as exc:
        _record_issue(reason, "Metrics update failed", exc)


def main():
    logger.info(">>> Detection Service: Stage 3 (Blind Consumer) <<<")
    runtime = Runtime()
    logger.info("Config summary: %s", Config.summary())

    health_host = os.getenv("HEALTH_BIND", "127.0.0.1")
    health_port = int(os.getenv("DETECTION_HEALTH_PORT", "9002"))
    state = ServiceState("detection")
    HealthServer(state, host=health_host, port=health_port).start_in_thread()
    state.set_check("config_loaded", True, details={"model": Config.MODEL_NAME, "bus_transport": Config.BUS_TRANSPORT})

    # initialize tracing (best-effort)
    try:
        ivis_tracing.init_tracer(service_name=os.getenv("OTEL_SERVICE_NAME", "detection"))
    except Exception as exc:
        _record_issue("tracing_init_failed", "Tracing init failed", exc)

    # Start Prometheus metrics server (best-effort)
    try:
        port = int(os.getenv("DETECTION_METRICS_PORT", "8002"))
        ivis_metrics.start_metrics_http_server(port)
        logger.info("Prometheus metrics HTTP server started on port %s", port)
    except Exception as exc:
        _record_issue("metrics_server_failed", "Failed to start metrics server", exc)

    try:
        model = load_model()
        runner = ModelRunner(model)
        runner.warmup()
        state.set_check(
            "model_loaded",
            True,
            details={"name": Config.MODEL_NAME, "path": Config.MODEL_PATH, "device": Config.MODEL_DEVICE, "img_size": Config.MODEL_IMG_SIZE},
        )

        consumer = FrameConsumer()
        consumer.connect()
        state.set_check("bus_connected", True, details={"transport": Config.BUS_TRANSPORT, "endpoint": Config.ZMQ_SUB_ENDPOINT})
        reader = MemoryReader()
        ok, details, err = reader.ensure_ring()
        state.set_check("shm_ready", ok, details=details, reason=err)
        state.compute_ready(["model_loaded", "bus_connected", "shm_ready"])
        decoder = FrameDecoder()
        publisher = ResultPublisher()

        logger.info(">>> Detection Loop Running <<<")

        for frame_contract in consumer:
            if not runtime.running:
                break

            state.touch_loop()
            state.inc("contracts_received", 1)
            state.set_check("bus_active", True)
            state.set_meta("last_contract_ts", time.time())

            if not state.get_check_ok("shm_ready"):
                ok, details, err = reader.ensure_ring()
                state.set_check("shm_ready", ok, details=details, reason=err)
                state.compute_ready(["model_loaded", "bus_connected", "shm_ready"])
                if not ok:
                    metrics.inc_dropped_reason("shm_not_ready")
                    _safe_metric(
                        "metrics_frames_dropped_failed",
                        lambda: ivis_metrics.frames_dropped_total.labels(reason="shm_not_ready").inc(),
                    )
                    continue

            metrics.inc_received()
            try:
                # frames in
                _safe_metric("metrics_frames_in_failed", ivis_metrics.frames_in_total.inc)

                # contract validation
                try:
                    validate_frame_contract_v1(frame_contract)
                except ContractValidationError as exc:
                    reason = getattr(exc, "reason_code", "validation_failed")
                    metrics.inc_dropped_reason(reason)
                    _safe_metric(
                        "metrics_frames_dropped_failed",
                        lambda: ivis_metrics.frames_dropped_total.labels(reason=reason).inc(),
                    )
                    logger.debug("Dropped frame due to contract validation: %s", getattr(exc, "message", str(exc)))
                    continue

                # stale frame
                if Config.MAX_FRAME_AGE_MS > 0:
                    now_ms = wall_clock_ms()
                    age_ms = latency_ms(now_ms, int(frame_contract.get("timestamp_ms", now_ms)))
                    if age_ms > Config.MAX_FRAME_AGE_MS:
                        metrics.inc_dropped()
                        _safe_metric(
                            "metrics_frames_dropped_failed",
                            lambda: ivis_metrics.frames_dropped_total.labels(reason="stale").inc(),
                        )
                        logger.debug("Dropped stale frame (age=%sms)", age_ms)
                        continue

                # SHM read (observe)
                try:
                    rr_start = time.time()
                    # trace SHM read
                    try:
                        with ivis_tracing.start_span("detection.shm_read", {"frame_id": frame_contract.get("frame_id"), "stream_id": frame_contract.get("stream_id")}):
                            raw_bytes = reader.read(frame_contract["memory"])
                    except Exception as exc:
                        _record_issue("tracing_span_shm_read_failed", "Tracing span failed (shm_read)", exc)
                        raw_bytes = reader.read(frame_contract["memory"])
                    rr_ms = (time.time() - rr_start) * 1000.0
                    _safe_metric("metrics_shm_read_latency_failed", lambda: ivis_metrics.shm_read_latency_ms.observe(rr_ms))
                except Exception as e:
                    logger.debug("SHM read failed: %s", str(e))
                    raw_bytes = None

                if raw_bytes is None:
                    metrics.inc_dropped()
                    _safe_metric(
                        "metrics_frames_dropped_failed",
                        lambda: ivis_metrics.frames_dropped_total.labels(reason="shm_read_failed").inc(),
                    )
                    continue

                # decode + inference
                frame = decoder.decode(raw_bytes, frame_contract)
                frame_id = frame_contract.get("frame_id")
                stream_id = frame_contract.get("stream_id")
                try:
                    inf_start = time.time()
                    # inference span
                    try:
                        with ivis_tracing.start_span("detection.inference", {"frame_id": frame_id, "stream_id": stream_id}):
                            raw_results = runner.infer(frame)
                        state.set_meta("last_infer_ts", time.time())
                        state.inc("frames_inferred", 1)
                    except Exception as exc:
                        _record_issue("tracing_span_inference_failed", "Tracing span failed (inference)", exc)
                        raw_results = runner.infer(frame)
                    inf_ms = (time.time() - inf_start) * 1000.0
                    _safe_metric("metrics_inference_latency_failed", lambda: ivis_metrics.inference_latency_ms.observe(inf_ms))
                except Exception:
                    raise

                # publish
                result = parse_output(frame_contract, raw_results)
                # publish span
                try:
                    with ivis_tracing.start_span("detection.publish", {"frame_id": frame_id, "stream_id": stream_id}):
                        publisher.publish(result)
                    state.set_meta("last_publish_ts", time.time())
                    state.inc("results_published", 1)
                    state.compute_ready(["model_loaded", "bus_connected", "shm_ready"])
                except Exception as exc:
                    _record_issue("tracing_span_publish_failed", "Tracing span failed (publish)", exc)
                    publisher.publish(result)
                _safe_metric("metrics_frames_out_failed", ivis_metrics.frames_out_total.inc)

                try:
                    ts = frame_contract.get("timestamp_ms")
                    if ts is not None:
                        now_ms = wall_clock_ms()
                        e2e = latency_ms(now_ms, int(ts))
                        _safe_metric("metrics_end_to_end_latency_failed", lambda: ivis_metrics.end_to_end_latency_ms.observe(e2e))
                except Exception as exc:
                    _record_issue("end_to_end_latency_failed", "End-to-end latency calculation failed", exc)

                metrics.inc_processed()

            except NonFatalError as e:
                metrics.inc_dropped()
                _safe_metric(
                    "metrics_frames_dropped_failed",
                    lambda: ivis_metrics.frames_dropped_total.labels(reason="nonfatal").inc(),
                )
                logger.debug("NonFatalError: %s", str(e))
                continue

            except FatalError as e:
                state.set_error("fatal_error", e, context=getattr(e, "context", None))
                state.set_ready(False)
                metrics.fatal_crashes += 1
                logger.error("FATAL ERROR: %s | Context: %s", getattr(e, 'message', str(e)), getattr(e, 'context', None))
                raise e

            except Exception as e:
                state.set_error("unhandled_exception", e, context={"frame_id": frame_contract.get("frame_id")})
                _safe_metric(
                    "metrics_frames_dropped_failed",
                    lambda: ivis_metrics.frames_dropped_total.labels(reason="unhandled_exception").inc(),
                )
                logger.error("Unhandled error processing frame (dropped): %s", str(e), exc_info=True)
                continue

    except FatalError:
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
