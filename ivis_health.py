# ivis_health.py
import json
import logging
import threading
import time
import os
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

    def _calc_derived_checks(self) -> Dict[str, Dict[str, Any]]:
        now = time.time()
        derived = {}

        # 1. loop_recent
        max_idle = float(os.getenv("READY_MAX_IDLE_SEC", "5"))
        if self.last_loop_ts:
            age = now - self.last_loop_ts
            ok = age <= max_idle
            derived["loop_recent"] = {
                "ok": ok,
                "ts": now,
                "reason": "idle_too_long" if not ok else None,
                "details": {"age_sec": round(age, 3), "max_sec": max_idle}
            }
        else:
             derived["loop_recent"] = {
                "ok": False,
                "ts": now,
                "reason": "never_started",
                "details": {}
            }

        # 2. bus_active_recent
        bus_ok = True
        reason = None
        details = {}
        
        if self.service == "ingestion":
            max_no_pub = float(os.getenv("READY_MAX_NO_PUBLISH_SEC", "10"))
            last_pub = self.meta.get("last_publish_ts")
            if last_pub:
                age = now - float(last_pub)
                if age > max_no_pub:
                    bus_ok = False
                    reason = "no_publish_recent"
                details = {"age_sec": round(age, 3), "max_sec": max_no_pub}
            else:
                bus_ok = False
                reason = "never_published"

        elif self.service == "detection":
            max_no_contract = float(os.getenv("READY_MAX_NO_CONTRACT_SEC", "10"))
            last_contract = self.meta.get("last_contract_ts")
            if last_contract:
                age = now - float(last_contract)
                if age > max_no_contract:
                    bus_ok = False
                    reason = "no_contract_recent"
                details = {"age_sec": round(age, 3), "max_sec": max_no_contract}
            else:
                bus_ok = False
                reason = "never_received_contract"
        
        derived["bus_active_recent"] = {
            "ok": bus_ok,
            "ts": now,
            "reason": reason,
            "details": details
        }
        
        return derived

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

    def snapshot(self, include_debug: bool = False) -> Dict[str, Any]:
        with self._lock:
            uptime = max(0.0, time.time() - self.start_ts)
            derived = self._calc_derived_checks()
            
            # Merit state = ready AND derived checks OK
            runtime_ready = self.ready and derived["loop_recent"]["ok"] and derived["bus_active_recent"]["ok"]

            # Merge derived checks into the main checks dict for visibility
            all_checks = self.checks.copy()
            all_checks.update(derived)

            return {
                "service": self.service,
                "uptime_sec": uptime,
                "ready": runtime_ready,  # Computed runtime readiness
                "config_ready": self.ready, # Original startup readiness
                "checks": all_checks,
                "counters": self.counters,
                "meta": self.meta,
                "last_loop_ts": self.last_loop_ts,
                "meta": self.meta,
                "last_loop_ts": self.last_loop_ts,
                # Filter out traceback/full error details unless strictly requested (authenticated)
                "last_error": self.last_error if include_debug else (
                    {k: v for k, v in self.last_error.items() if k not in ("traceback", "context")} 
                    if self.last_error else None
                ),
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
                # Strict Token Check for /state
                required_token = os.getenv("HEALTH_TOKEN")
                if not required_token:
                    self._write_json(403, {"error": "forbidden", "detail": "HEALTH_TOKEN not configured"})
                    return
                
                auth_header = self.headers.get("X-IVIS-Health-Token")
                if auth_header != required_token:
                    self._write_json(403, {"error": "forbidden", "detail": "invalid token"})
                    return

                self._write_json(200, state.snapshot(include_debug=True))
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
        if not os.getenv("HEALTH_TOKEN"):
            logger.warning("SECURITY WARNING: HEALTH_TOKEN is not set. /state endpoint will be inaccessible.")
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
