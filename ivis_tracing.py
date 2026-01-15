"""ivis_tracing: optional OpenTelemetry tracing helper.

Usage:
  from ivis_tracing import init_tracer, start_span
  init_tracer(service_name="ingestion")
  with start_span("capture", {"frame_id": fid, "stream_id": sid}):
      ...

This module is best-effort: if OpenTelemetry packages are not installed
or initialization fails, start_span becomes a no-op context manager so
tracing is optional and won't break runtime.
"""
import os
import contextlib
from typing import Optional, Mapping

_tracer = None
_enabled = False


def init_tracer(service_name: Optional[str] = None):
    """Initialize OpenTelemetry tracer using environment variables.

    Env vars used:
      OTEL_EXPORTER_OTLP_ENDPOINT - OTLP HTTP endpoint (e.g. http://collector:4318)
      OTEL_SERVICE_NAME - service.name override
      OTEL_SAMPLER - always_on | always_off | traceidratio
      OTEL_SAMPLE_RATE - for traceidratio, float between 0.0 and 1.0
    """
    global _tracer, _enabled
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.sampling import AlwaysOnSampler, AlwaysOffSampler, TraceIdRatioBased

        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        env_name = os.getenv("OTEL_SERVICE_NAME") or service_name or "ivis"
        sampler_mode = os.getenv("OTEL_SAMPLER", "always_on").lower()
        sample_rate = float(os.getenv("OTEL_SAMPLE_RATE", "1.0"))

        if sampler_mode == "always_off":
            sampler = AlwaysOffSampler()
        elif sampler_mode == "traceidratio":
            sampler = TraceIdRatioBased(sample_rate)
        else:
            sampler = AlwaysOnSampler()

        provider = TracerProvider(sampler=sampler)
        trace.set_tracer_provider(provider)

        if endpoint:
            exporter = OTLPSpanExporter(endpoint=endpoint)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)

        _tracer = trace.get_tracer(env_name)
        _enabled = True
    except Exception:
        # tracing disabled; keep no-op behavior
        _tracer = None
        _enabled = False


@contextlib.contextmanager
def start_span(name: str, attributes: Optional[Mapping[str, object]] = None):
    """Context manager that starts a span if tracing is enabled, else no-op."""
    global _tracer, _enabled
    if not _enabled or _tracer is None:
        yield None
        return
    try:
        with _tracer.start_as_current_span(name) as span:
            if attributes:
                try:
                    for k, v in attributes.items():
                        if v is not None:
                            span.set_attribute(str(k), v)
                except Exception:
                    pass
            yield span
    except Exception:
        # swallow tracing errors
        yield None


def is_enabled() -> bool:
    return bool(_enabled)
