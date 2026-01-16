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

    def close(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception as exc:
                print(f"[DETECTION] Error closing Postgres connection: {exc}")
            self.conn = None


class ZmqResultWriter:
    def __init__(self, endpoint: str):
        try:
            import zmq
        except Exception as exc:
            raise FatalError("Missing ZeroMQ dependency", context={"error": str(exc)}) from exc
        self.zmq = zmq
        self.endpoint = endpoint
        self.socket = self.zmq.Context.instance().socket(self.zmq.PUB)
        self.socket.setsockopt(self.zmq.LINGER, Config.ZMQ_LINGER_MS)
        self.socket.bind(self.endpoint)

    def write(self, result: dict):
        payload = json.dumps(result).encode("utf-8")
        try:
            self.socket.send(payload)
        except Exception as exc:
            import logging
            logging.getLogger("detection").error("ZMQ results publish failed: %s", exc)
            return

    def close(self):
        if self.socket:
            try:
                self.socket.close()
            except Exception as exc:
                import logging
                logging.getLogger("detection").debug("Error closing ZMQ socket: %s", exc)
            self.socket = None


class ResultPublisher:
    def __init__(self):
        self.logger = setup_logging("detection")
        self.pg_writer = None
        self.zmq_writer = None
        if Config.POSTGRES_DSN:
            try:
                self.pg_writer = PostgresWriter(Config.POSTGRES_DSN)
                self.logger.info("Postgres writer enabled.")
            except Exception as exc:
                self.logger.error("Postgres writer disabled: %s", exc)
        if Config.ZMQ_RESULTS_PUB_ENDPOINT:
            try:
                self.zmq_writer = ZmqResultWriter(Config.ZMQ_RESULTS_PUB_ENDPOINT)
                self.logger.info("ZMQ results publisher enabled.")
            except Exception as exc:
                self.logger.error("ZMQ results publisher disabled: %s", exc)

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
            if self.zmq_writer:
                self.zmq_writer.write(result)
        except Exception as e:
            raise FatalError("Publish failed", context={"error": str(e)})

    def close(self):
        if self.zmq_writer:
            try:
                self.zmq_writer.close()
            except Exception as exc:
                self.logger.debug("Error closing ZMQ writer: %s", exc)
        if self.pg_writer:
            try:
                self.pg_writer.close()
            except Exception as exc:
                self.logger.debug("Error closing Postgres writer: %s", exc)
