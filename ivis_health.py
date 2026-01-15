# ivis_health.py
import json
import logging
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional

logger = logging.getLogger("health")


class ServiceState:
    def __init__(self, service: str):
        self.service = service
        self.start_ts = time.time()
        self._lock = threading.Lock()

        self.ready: bool = False
        self.checks: Dict[str, Dict[str, Any]] = {}
        self.counters: Dict[str, int] = {}
        self.meta: Dict[str, Any] = {}

        self.last_loop_ts: Optional[float] = None
        self.last_error: Optional[Dict[str, Any]] = None

    def set_check(self, name: str, ok: bool, details: Optional[Dict[str, Any]] = None, reason: Optional[str] = None) -> None:
        with self._lock:
            self.checks[name] = {
                "ok": bool(ok),
                "ts": time.time(),
                "reason": reason,
                "details": details or {},
            }

    def get_check_ok(self, name: str) -> bool:
        with self._lock:
            return bool(self.checks.get(name, {}).get("ok", False))

    def inc(self, name: str, by: int = 1) -> None:
        if by == 0:
            return
        with self._lock:
            self.counters[name] = int(self.counters.get(name, 0)) + int(by)

    def set_meta(self, key: str, value: Any) -> None:
        with self._lock:
            self.meta[key] = value

    def touch_loop(self) -> None:
        with self._lock:
            self.last_loop_ts = time.time()

    def set_ready(self, ready: bool) -> None:
        with self._lock:
            self.ready = bool(ready)

    def compute_ready(self, required_checks: list) -> bool:
        ok = True
        for name in required_checks:
            if not self.get_check_ok(name):
                ok = False
                break
        self.set_ready(ok)
        return ok

    def set_error(self, reason: str, exc: Optional[BaseException] = None, context: Optional[Dict[str, Any]] = None) -> None:
        payload = {
            "ts": time.time(),
            "reason": reason,
            "context": context or {},
        }
        if exc is not None:
            payload["error"] = str(exc)
            payload["traceback"] = traceback.format_exc()
        with self._lock:
            self.last_error = payload

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            uptime = max(0.0, time.time() - self.start_ts)
            return {
                "service": self.service,
                "uptime_sec": uptime,
                "ready": self.ready,
                "checks": self.checks,
                "counters": self.counters,
                "meta": self.meta,
                "last_loop_ts": self.last_loop_ts,
                "last_error": self.last_error,
            }


class _Handler(BaseHTTPRequestHandler):
    server_version = "IVISHealth/1.0"

    def _write_json(self, status: int, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        state: ServiceState = self.server.state  # type: ignore[attr-defined]
        try:
            if self.path == "/health":
                snap = state.snapshot()
                self._write_json(200, snap)
                return

            if self.path == "/ready":
                snap = state.snapshot()
                status = 200 if snap.get("ready") else 503
                self._write_json(status, snap)
                return

            if self.path == "/state":
                self._write_json(200, state.snapshot())
                return

            self._write_json(404, {"error": "not_found", "path": self.path})
        except Exception as exc:
            logger.exception("Health handler failed: %s", exc)
            self._write_json(500, {"error": "internal_error", "detail": str(exc)})

    def log_message(self, fmt: str, *args):  # silence default noisy logs
        return


class HealthServer:
    def __init__(self, state: ServiceState, host: str, port: int):
        self.state = state
        self.host = host
        self.port = int(port)
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start_in_thread(self) -> None:
        httpd = ThreadingHTTPServer((self.host, self.port), _Handler)
        httpd.state = self.state  # type: ignore[attr-defined]
        self._httpd = httpd

        t = threading.Thread(target=httpd.serve_forever, name=f"{self.state.service}-health", daemon=True)
        t.start()
        self._thread = t

    def stop(self) -> None:
        if self._httpd is None:
            return
        try:
            self._httpd.shutdown()
        except Exception:
            pass
