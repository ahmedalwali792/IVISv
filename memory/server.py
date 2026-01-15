# FILE: memory/server.py
# ------------------------------------------------------------------------------
import http.server
import socketserver
import sys
import os
import json

from memory.runtime import Runtime
from ivis_logging import setup_logging

logger = setup_logging("memory")



# Global Init - If this fails, script dies (Stage 2 compliant)
try:
    runtime = Runtime()
    runtime.initialize()
    backend = runtime.get_backend()
except Exception as e:
    logger.error("FATAL: Memory Service Init Failed - %s", str(e))
    sys.exit(1)

class MemoryRequestHandler(http.server.BaseHTTPRequestHandler):
    
    def do_PUT(self):
        try:
            key = self.path.strip("/")
            try:
                length = int(self.headers['Content-Length'])
                data = self.rfile.read(length)
            except (TypeError, ValueError):
                self.send_error(400, "Invalid Content-Length")
                return
            
            ref = backend.put(key, data)
            
            if ref:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                resp = {"size": ref.size, "generation": ref.generation}
                self.wfile.write(json.dumps(resp).encode())
            else:
                self.send_error(507, "Memory Write Failed")
                
        except Exception:
            self.send_error(500, "Internal Server Error")

    def do_GET(self):
        try:
            key = self.path.strip("/")
            data = backend.get(key)
            
            if data:
                self.send_response(200)
                self.send_header('Content-type', 'application/octet-stream')
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(404, "Frame not found")
        except Exception:
             self.send_error(500, "Internal Server Error")

    def do_HEAD(self):
        # Support simple health probes via HEAD /health
        if self.path.strip("/") == "health":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            return
        else:
            self.send_error(404)

    def do_POST(self):
        # Add a simple JSON health endpoint at POST /health (optional)
        if self.path.strip("/") == "health":
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
            return
        self.send_error(404)

    def log_message(self, format, *args):
        # suppress default http.server logging
        return

PORT = 6000

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    try:
        class ThreadingHTTPServer(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = True

        with ThreadingHTTPServer(("", PORT), MemoryRequestHandler) as httpd:
            print(f"[MEMORY SERVER] Running on port {PORT} (Threaded)")
            httpd.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"FATAL: Server Crash - {e}")
        sys.exit(1)
