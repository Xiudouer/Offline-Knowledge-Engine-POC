"""Local browser API; no URL import, external assets, public bind or request logging."""
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import unquote

from .docreader import MAX_FILE
from .engine import Engine
from .net import EngineError, Ollama
from .store import Store


def main():
    token = os.environ.get("OKE_ACCESS_TOKEN", "")
    password = os.environ.get("OKE_DB_PASSWORD", "")
    if len(token) < 32 or len(password) < 32:
        raise RuntimeError("Private local credentials are required")
    public_port = int(os.environ.get("OKE_PUBLIC_PORT", "18787"))
    allowed_hosts = {f"127.0.0.1:{public_port}", f"localhost:{public_port}", "127.0.0.1:8080", "localhost:8080"}
    allowed_origins = {"http://" + host for host in allowed_hosts}
    assets = Path(__file__).resolve().parent / "web"
    engine = Engine(Store(password=password), Ollama())
    ready = False
    ready_lock = threading.Lock()

    def ensure_ready():
        nonlocal ready
        with ready_lock:
            if not ready:
                engine.ready()
                ready = True

    class Handler(BaseHTTPRequestHandler):
        server_version = "OfflineKnowledgeEngine"
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def respond(self, status, payload, content_type="application/json; charset=utf-8"):
            body = json.dumps(payload, ensure_ascii=True, allow_nan=False).encode() if isinstance(payload, (dict, list)) else payload
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

        def handle_api(self):
            self.close_connection = True
            try:
                if (self.headers.get("Host") not in allowed_hosts or self.headers.get("Transfer-Encoding")
                        or len(self.headers.get_all("Authorization", [])) > 1 or
                        len(self.headers.get_all("Content-Length", [])) > 1):
                    raise EngineError("invalid_request", 400)
                if self.headers.get("Origin") and self.headers["Origin"] not in allowed_origins:
                    raise EngineError("origin_forbidden", 403)
                path = self.path
                if self.command == "GET" and path in {"/", "/app.js", "/style.css"}:
                    name = "index.html" if path == "/" else path[1:]
                    content_type = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "style.css": "text/css; charset=utf-8"}[name]
                    self.respond(200, (assets / name).read_bytes(), content_type)
                    return
                authorization = self.headers.get("Authorization", "")
                if not hmac.compare_digest(authorization.encode(), ("Bearer " + token).encode()):
                    raise EngineError("unauthenticated", 401)
                if path == "/api/status" and self.command == "GET":
                    ensure_ready()
                    self.respond(200, {"ready": True, "mode": "local-only", "models": ["qwen3:0.6b", "qwen3-embedding:0.6b"]})
                    return
                if path == "/api/documents" and self.command == "GET":
                    ensure_ready()
                    self.respond(200, {"documents": engine.store.documents()})
                    return
                if self.command not in {"POST", "DELETE"}:
                    raise EngineError("route_not_found", 404)
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    raise EngineError("invalid_content_length") from None
                if not 0 < length <= MAX_FILE:
                    raise EngineError("request_size_limit", 413)
                body = self.rfile.read(length)
                if len(body) != length:
                    raise EngineError("incomplete_upload")
                ensure_ready()
                if path == "/api/ingest" and self.command == "POST":
                    filename = unquote(self.headers.get("X-Filename", ""), errors="strict")
                    result = engine.ingest(filename, body)
                elif path in {"/api/ask", "/api/delete"} and self.command == "POST":
                    if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
                        raise EngineError("json_required")
                    item = json.loads(body)
                    if path == "/api/ask" and set(item) == {"question"}:
                        result = engine.ask(item["question"])
                    elif path == "/api/delete" and set(item) == {"id"}:
                        result = engine.store.delete(item["id"])
                    else:
                        raise EngineError("unexpected_fields")
                else:
                    raise EngineError("route_not_found", 404)
                self.respond(200, result)
            except EngineError as error:
                self.respond(error.status, {"error": error.code})
            except Exception:
                self.respond(503, {"error": "local_service_unavailable"})

        do_GET = do_POST = do_DELETE = handle_api

        def log_message(self, *_args):
            pass  # No document, query, token, file name or exception body in access logs.

    class BoundedServer(ThreadingHTTPServer):
        daemon_threads = True
        slots = threading.BoundedSemaphore(8)

        def process_request(self, request, address):
            if not self.slots.acquire(False):
                self.shutdown_request(request)
                return
            try:
                super().process_request(request, address)
            except Exception:
                self.slots.release()
                raise

        def process_request_thread(self, request, address):
            try:
                super().process_request_thread(request, address)
            finally:
                self.slots.release()

        def handle_error(self, *_args):
            pass

    server = BoundedServer(("0.0.0.0", 8080), Handler)
    print("OfflineKnowledgeEngine: local UI ready; models and database checked on authenticated request.", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
