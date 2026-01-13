# FILE: detection/publish/results.py
# ------------------------------------------------------------------------------
import json

from detection.config import Config
from detection.errors.fatal import FatalError
from ivis_logging import setup_logging
from ivis.common.contracts.result_contract import validate_result_contract_v1


class PostgresWriter:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.conn = None
        self._connect()

    def _connect(self):
        try:
            import psycopg2
        except Exception as exc:
            raise FatalError("Missing psycopg2 dependency", context={"error": str(exc)}) from exc

        self.conn = psycopg2.connect(self.dsn)
        self.conn.autocommit = True
        with self.conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS detection_results (
                    id SERIAL PRIMARY KEY,
                    frame_id TEXT NOT NULL,
                    stream_id TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    timestamp BIGINT NOT NULL,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )

    def write(self, result: dict):
        if not self.conn:
            return
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO detection_results (frame_id, stream_id, camera_id, timestamp, payload)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    result.get("frame_id"),
                    result.get("stream_id"),
                    result.get("camera_id"),
                    result.get("timestamp_ms"),
                    json.dumps(result),
                ),
            )


class RedisResultWriter:
    def __init__(self, url: str, stream: str, mode: str, channel: str):
        try:
            import redis
        except Exception as exc:
            raise FatalError("Missing Redis dependency", context={"error": str(exc)}) from exc
        self.redis = redis.Redis.from_url(url)
        self.stream = stream
        self.mode = mode.lower()
        self.channel = channel
        import os
        try:
            self.stream_maxlen = int(os.getenv("REDIS_RESULTS_STREAM_MAXLEN", "2000"))
        except Exception:
            self.stream_maxlen = 2000

    def write(self, result: dict):
        payload = json.dumps(result)
        try:
            if self.mode == "pubsub":
                self.redis.publish(self.channel, payload)
            else:
                # Append result then trim to retention window to avoid unbounded growth
                self.redis.xadd(self.stream, {"payload": payload})
                try:
                    self.redis.xtrim(self.stream, maxlen=self.stream_maxlen, approximate=False)
                except Exception:
                    # Best-effort trimming; don't fail publish on trim errors
                    pass
        except Exception as exc:
            import logging
            logging.getLogger("detection").error("Redis results publish failed: %s", exc)
            return


class ResultPublisher:
    def __init__(self):
        self.logger = setup_logging("detection")
        self.pg_writer = None
        self.redis_writer = None
        if Config.POSTGRES_DSN:
            try:
                self.pg_writer = PostgresWriter(Config.POSTGRES_DSN)
                self.logger.info("Postgres writer enabled.")
            except Exception as exc:
                self.logger.error("Postgres writer disabled: %s", exc)
        if Config.REDIS_URL and Config.REDIS_RESULTS_STREAM:
            try:
                self.redis_writer = RedisResultWriter(
                    Config.REDIS_URL,
                    Config.REDIS_RESULTS_STREAM,
                    Config.REDIS_MODE,
                    Config.REDIS_RESULTS_CHANNEL,
                )
                self.logger.info("Redis results stream enabled.")
            except Exception as exc:
                self.logger.error("Redis results stream disabled: %s", exc)

    def publish(self, result: dict):
        # Populate model metadata
        model_meta = {
            "name": Config.MODEL_NAME,
            "version": Config.MODEL_VERSION,
            "threshold": Config.MODEL_CONF,
            "input_size": [Config.MODEL_IMG_SIZE, Config.MODEL_IMG_SIZE],
        }
        result["model"] = model_meta

        # Ensure timing present
        timing = result.get("timing")
        if timing is None or not isinstance(timing, dict):
            timing = {}
            result["timing"] = timing
        timing.setdefault("inference_ms", 0.0)

        # Validate result contract v1 before publishing
        try:
            validate_result_contract_v1(result)
        except Exception as exc:
            # Validation failure should not crash service; surface as Fatal to caller
            raise FatalError("ResultContractV1 validation failed", context={"error": str(exc)}) from exc

        try:
            payload = json.dumps(result)
            print(f"[RESULT] {payload}")
            if self.pg_writer:
                self.pg_writer.write(result)
            if self.redis_writer:
                self.redis_writer.write(result)
        except Exception as e:
            raise FatalError("Publish failed", context={"error": str(e)})
