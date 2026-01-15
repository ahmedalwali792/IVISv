# Architecture Notes — IVISv

Production message bus: Redis Streams

- Frames are produced by `ingestion` into the Redis stream `ivis:frames` using `XADD`.
- Detection runs as a consumer group `ivis:detection` and consumes frames using `XREADGROUP`.
- Results are written to `ivis:results` (XADD) and can be consumed by the UI or other services.

Why Redis Streams?

- Persistent log with consumer groups enables replay, monitoring of pending entries, and robust backpressure.
- Simpler operational model than managing a custom TCP bus or an always-running ZMQ proxy.

Legacy transports

- Legacy or developer-only transports have been moved to `ivis/legacy/` to keep the canonical production path clear. Examples:
  - TCP/simple Socket bus (dev-only)
  - ZeroMQ proxy (dev-only)
  - Redis PubSub helper code (kept for backward compatibility)
  - Local HTTP memory server used in early development

Contract: frames on `ivis:frames`

- Each stream entry contains a JSON `FrameContractV1` payload under a `payload` field.
- Downstream services assume frames are in the `FRAME_COLOR_SPACE` (v1 contract = `bgr`). Ingestion is responsible for converting the raw `SOURCE_COLOR` into the canonical `FRAME_COLOR_SPACE` before publishing.
