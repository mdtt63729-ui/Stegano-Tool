#!/usr/bin/env python3
"""
Local web UI for Stegano Tool.

Stdlib only. Multipart bodies are parsed with email.parser (works on Python
3.8 through 3.13+, unlike the removed cgi module), and every produced file is
exposed through a one-time download route so the browser can actually save it.
"""
from __future__ import annotations

import json
import mimetypes
import secrets
import tempfile
import threading
import webbrowser
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import BUILD, VERSION
from .core import describe, pack, strip, unpack

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
MAX_BODY = 512 * 1024 * 1024  # 512 MB


class Store:
    """Keeps produced files in a temp dir and hands out opaque tokens."""

    def __init__(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="stegano-"))
        self.files: dict[str, Path] = {}
        self.lock = threading.Lock()

    def add(self, path: Path) -> str:
        token = secrets.token_urlsafe(16)
        with self.lock:
            self.files[token] = path
        return token

    def get(self, token: str) -> Path | None:
        with self.lock:
            return self.files.get(token)


STORE = Store()


def parse_multipart(body: bytes, content_type: str) -> dict[str, dict]:
    """Return {field: {'filename': str|None, 'data': bytes}} from a body."""
    if "multipart/form-data" not in content_type.lower():
        return {}
    msg = BytesParser(policy=email_policy).parsebytes(
        b"Content-Type: " + content_type.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
    )
    fields: dict[str, dict] = {}
    if not msg.is_multipart():
        return fields
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        fields[name] = {
            "filename": part.get_filename(),
            "data": payload,
        }
    return fields


class Handler(BaseHTTPRequestHandler):
    server_version = f"SteganoTool/{VERSION}"

    # ------------------------------------------------------------------ #
    def _send(self, code=200, body: bytes = b"", ctype="text/html; charset=utf-8",
              extra_headers: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode(), "application/json")

    def log_message(self, fmt, *args):  # quieter console
        return

    # ------------------------------------------------------------------ #
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            page = WEB / "index.html"
            if not page.exists():
                self._send(500, b"web/index.html is missing from the install.")
                return
            self._send(200, page.read_bytes())
            return
        if path.startswith("/download/"):
            token = path[len("/download/"):]
            stored = STORE.get(token)
            if stored is None or not stored.exists():
                self._send(404, b"File expired or unknown token.")
                return
            ctype = mimetypes.guess_type(stored.name)[0] or "application/octet-stream"
            self._send(
                200,
                stored.read_bytes(),
                ctype,
                {"Content-Disposition": f'attachment; filename="{stored.name}"'},
            )
            return
        if path == "/health":
            self._json(200, {"ok": True, "version": VERSION, "build": BUILD})
            return
        self._send(404, b"Not found")

    def do_HEAD(self):
        self.do_GET()

    # ------------------------------------------------------------------ #
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                raise ValueError("Empty request body.")
            if length > MAX_BODY:
                raise ValueError("Request too large.")
            body = self.rfile.read(length)
            fields = parse_multipart(body, self.headers.get("Content-Type", ""))
            action = (fields.get("action", {}).get("data") or b"").decode().strip()
            password = (fields.get("password", {}).get("data") or b"").decode() or None

            image = fields.get("image")
            if not image or not image["data"]:
                raise ValueError("A PNG image is required.")
            image_bytes = image["data"]

            if action == "inspect":
                self._json(200, {"ok": True, "data": describe(image_bytes)})
                return

            if action == "hide":
                payload = fields.get("payload")
                if not payload or not payload["data"]:
                    raise ValueError("A file to embed is required.")
                name = Path(payload["filename"] or "payload.bin").name
                out = STORE.dir / "stegano_output.png"
                out.write_bytes(pack(image_bytes, payload["data"], name, password))
                token = STORE.add(out)
                self._json(200, {
                    "ok": True,
                    "file": out.name,
                    "size": out.stat().st_size,
                    "embedded": name,
                    "download": f"/download/{token}",
                })
                return

            if action == "extract":
                record, data = unpack(image_bytes, password)
                name = Path(record.get("name") or "payload.bin").name
                out = STORE.dir / name
                out.write_bytes(data)
                token = STORE.add(out)
                self._json(200, {
                    "ok": True,
                    "file": out.name,
                    "size": len(data),
                    "download": f"/download/{token}",
                })
                return

            if action == "remove":
                out = STORE.dir / "stegano_clean.png"
                out.write_bytes(strip(image_bytes))
                token = STORE.add(out)
                self._json(200, {
                    "ok": True,
                    "file": out.name,
                    "size": out.stat().st_size,
                    "download": f"/download/{token}",
                })
                return

            raise ValueError("Unknown action.")
        except ValueError as exc:
            self._json(400, {"ok": False, "error": str(exc)})
        except Exception as exc:  # never fail silently
            self._json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def serve(host: str = "127.0.0.1", port: int = 8080, open_browser: bool = True):
    try:
        httpd = ThreadingHTTPServer((host, port), Handler)
    except OSError as exc:
        raise ValueError(
            f"Cannot listen on {host}:{port} ({exc}). Try --port {port + 1}."
        ) from exc

    url = f"http://{host}:{port}"
    print(f"\nStegano Tool {VERSION} (build {BUILD})")
    print(f"Web UI: {url}")
    print(f"Files land in: {STORE.dir}")
    print("Press Ctrl+C to stop.\n")

    if open_browser:
        try:
            import subprocess

            subprocess.Popen(
                ["am", "start", "-a", "android.intent.action.VIEW", "-d", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            try:
                webbrowser.open(url)
            except Exception:
                pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
