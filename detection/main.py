#!/usr/bin/env python
import sys
import os
import time

from ivis_logging import setup_logging
logger = setup_logging("detection")

import ivis_metrics
import ivis_tracing
from ivis.common.time_utils import latency_ms, wall_clock_ms

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


def main():
    logger.info(">>> Detection Service: Stage 3 (Blind Consumer) <<<")
    runtime = Runtime()
    logger.info("Config summary: %s", Config.summary())

    # initialize tracing (best-effort)
    try:
        ivis_tracing.init_tracer(service_name=os.getenv("OTEL_SERVICE_NAME", "detection"))
    except Exception:
        pass

    # Start Prometheus metrics server (best-effort)
    try:
        port = int(os.getenv("DETECTION_METRICS_PORT", "8002"))
        ivis_metrics.start_metrics_http_server(port)
        logger.info("Prometheus metrics HTTP server started on port %s", port)
    except Exception:
        logger.exception("Failed to start metrics server")

    try:
        model = load_model()
        runner = ModelRunner(model)
        runner.warmup()

        consumer = FrameConsumer()
        reader = MemoryReader()
        decoder = FrameDecoder()
        publisher = ResultPublisher()

        logger.info(">>> Detection Loop Running <<<")

        for frame_contract in consumer:
            if not runtime.running:
                break

            metrics.inc_received()
            try:
                # frames in
                try:
                    ivis_metrics.frames_in_total.inc()
                except Exception:
                    pass

                # contract validation
                try:
                    validate_frame_contract_v1(frame_contract)
                except ContractValidationError as exc:
                    reason = getattr(exc, "reason_code", "validation_failed")
                    metrics.inc_dropped_reason(reason)
                    try:
                        ivis_metrics.frames_dropped_total.labels(reason=reason).inc()
                    except Exception:
                        pass
                    logger.debug("Dropped frame due to contract validation: %s", getattr(exc, "message", str(exc)))
                    continue

                # stale frame
                if Config.MAX_FRAME_AGE_MS > 0:
                    now_ms = wall_clock_ms()
                    age_ms = latency_ms(now_ms, int(frame_contract.get("timestamp_ms", now_ms)))
                    if age_ms > Config.MAX_FRAME_AGE_MS:
                        metrics.inc_dropped()
                        try:
                            ivis_metrics.frames_dropped_total.labels(reason="stale").inc()
                        except Exception:
                            pass
                        logger.debug("Dropped stale frame (age=%sms)", age_ms)
                        continue

                # SHM read (observe)
                try:
                    rr_start = time.time()
                    # trace SHM read
                    try:
                        with ivis_tracing.start_span("detection.shm_read", {"frame_id": frame_contract.get("frame_id"), "stream_id": frame_contract.get("stream_id")}):
                            raw_bytes = reader.read(frame_contract["memory"])
                    except Exception:
                        raw_bytes = reader.read(frame_contract["memory"])
                    rr_ms = (time.time() - rr_start) * 1000.0
                    try:
                        ivis_metrics.shm_read_latency_ms.observe(rr_ms)
                    except Exception:
                        pass
                except Exception:
                    raw_bytes = None

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
                    except Exception:
                        raw_results = runner.infer(frame)
                    inf_ms = (time.time() - inf_start) * 1000.0
                    try:
                        ivis_metrics.inference_latency_ms.observe(inf_ms)
                    except Exception:
                        pass
                except Exception:
                    raise

                # publish
                result = parse_output(frame_contract, raw_results)
                # publish span
                try:
                    with ivis_tracing.start_span("detection.publish", {"frame_id": frame_id, "stream_id": stream_id}):
                        publisher.publish(result)
                except Exception:
                    publisher.publish(result)
                try:
                    ivis_metrics.frames_out_total.inc()
                except Exception:
                    pass

                try:
                    ts = frame_contract.get("timestamp_ms")
                    if ts is not None:
                        now_ms = wall_clock_ms()
                        e2e = latency_ms(now_ms, int(ts))
                        ivis_metrics.end_to_end_latency_ms.observe(e2e)
                except Exception:
                    pass

                metrics.inc_processed()

            except NonFatalError as e:
                metrics.inc_dropped()
                try:
                    ivis_metrics.frames_dropped_total.labels(reason="nonfatal").inc()
                except Exception:
                    pass
                logger.debug("NonFatalError: %s", str(e))
                continue

            except FatalError as e:
                metrics.fatal_crashes += 1
                logger.error("FATAL ERROR: %s | Context: %s", getattr(e, 'message', str(e)), getattr(e, 'context', None))
                raise e

            except Exception as e:
                try:
                    ivis_metrics.frames_dropped_total.labels(reason="unhandled_exception").inc()
                except Exception:
                    pass
                logger.exception("Unhandled crash: %s", str(e))
                raise FatalError(f"Unexpected: {e}")

    except FatalError:
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
