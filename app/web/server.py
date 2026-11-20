"""
Friday Web Studio Server.
Local, privacy-first, offline web server for audio/video transcription and translation.
Powered by NVIDIA RTX 4060 GPU (CUDA float16) via Faster-Whisper.
Runs on http://127.0.0.1:8765
"""
import cgi
import io
import json
import mimetypes
import os
import re
import sys
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional, Tuple

import pyperclip

from app.core.formatters import segments_to_srt, segments_to_txt, segments_to_vtt
from app.core.whisper_engine import WhisperEngine

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
HTML_FILE = os.path.join(STATIC_DIR, "index.html")

# Global engine instance for Web Studio
_engine_lock = threading.Lock()
_global_engine: Optional[WhisperEngine] = None


def get_web_engine(model_name: str = "large-v3-turbo") -> WhisperEngine:
    """Retrieve or initialize the shared Whisper engine for Web Studio."""
    global _global_engine
    with _engine_lock:
        if _global_engine is None:
            _global_engine = WhisperEngine(
                model_name=model_name,
                device="cuda",
                compute_type="float16",
                language=None,
                vad_filter=True,
            )
            _global_engine.load_model()
        elif _global_engine.model_name != model_name:
            print(f"[WebStudio] Switching engine model from {_global_engine.model_name} to {model_name}...")
            _global_engine.load_model(model_name)
        return _global_engine


def parse_multipart_form_data(
    body: bytes, boundary: str
) -> Tuple[Dict[str, str], Optional[Tuple[str, bytes]]]:
    """
    Robust pure-Python multipart/form-data parser.
    Returns (form_fields_dict, (filename, file_bytes) or None).
    """
    fields: Dict[str, str] = {}
    file_info: Optional[Tuple[str, bytes]] = None

    boundary_bytes = ("--" + boundary).encode("latin-1")
    parts = body.split(boundary_bytes)

    for part in parts:
        if not part or part == b"--\r\n" or part == b"--" or part.startswith(b"--"):
            continue

        # Split headers and body
        if b"\r\n\r\n" not in part:
            continue
        raw_headers, content = part.split(b"\r\n\r\n", 1)
        # Trim trailing \r\n from content
        if content.endswith(b"\r\n"):
            content = content[:-2]

        headers_str = raw_headers.decode("latin-1", errors="replace")
        disp_match = re.search(r'Content-Disposition:\s*form-data;\s*name="([^"]+)"(?:;\s*filename="([^"]+)")?', headers_str, re.IGNORECASE)
        if not disp_match:
            continue

        field_name = disp_match.group(1)
        filename = disp_match.group(2)

        if filename:
            file_info = (filename, content)
        else:
            fields[field_name] = content.decode("utf-8", errors="replace")

    return fields, file_info


class WebStudioHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Keep console output clean
        sys.stderr.write(f"[WebStudio] {args[0]} {args[1]} {args[2]}\n")

    def _send_json(self, status_code: int, data: Dict[str, Any]):
        response_bytes = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ["/", "/index.html"]:
            if not os.path.exists(HTML_FILE):
                self.send_error(404, "index.html not found")
                return
            with open(HTML_FILE, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        if path == "/api/status":
            engine = get_web_engine()
            self._send_json(200, {
                "status": "ready" if engine.is_ready else "loading",
                "model": engine.model_name,
                "device": engine.active_device,
                "compute_type": engine.compute_type,
                "supported_models": [
                    "large-v3-turbo",
                    "large-v3",
                    "medium",
                    "small",
                    "base",
                    "tiny",
                ],
                "gpu_name": "NVIDIA GeForce RTX 4060 Laptop GPU",
            })
            return

        # Serve other static files if any
        local_path = os.path.join(STATIC_DIR, path.lstrip("/"))
        if os.path.isfile(local_path):
            mime_type, _ = mimetypes.guess_type(local_path)
            with open(local_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/copy":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8", errors="replace")
            try:
                data = json.loads(body)
                text_to_copy = data.get("text", "")
                if text_to_copy:
                    pyperclip.copy(text_to_copy)
                    self._send_json(200, {"success": True, "message": "Copied to clipboard"})
                else:
                    self._send_json(400, {"success": False, "error": "No text provided"})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return

        if path == "/api/export":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8", errors="replace")
            try:
                data = json.loads(body)
                segments = data.get("segments", [])
                fmt = data.get("format", "txt").lower()
                filename = data.get("filename", "transcript")

                if fmt == "srt":
                    content = segments_to_srt(segments)
                    ext = "srt"
                    mime = "text/plain; charset=utf-8"
                elif fmt == "vtt":
                    content = segments_to_vtt(segments)
                    ext = "vtt"
                    mime = "text/vtt; charset=utf-8"
                else:
                    content = segments_to_txt(segments)
                    ext = "txt"
                    mime = "text/plain; charset=utf-8"

                content_bytes = content.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Disposition", f'attachment; filename="{filename}.{ext}"')
                self.send_header("Content-Length", str(len(content_bytes)))
                self.end_headers()
                self.wfile.write(content_bytes)
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})
            return

        if path == "/api/transcribe":
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._send_json(400, {"success": False, "error": "Expected multipart/form-data"})
                return

            boundary_match = re.search(r'boundary=([^;]+)', content_type)
            if not boundary_match:
                self._send_json(400, {"success": False, "error": "Missing boundary in Content-Type"})
                return
            boundary = boundary_match.group(1).strip('"')

            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 500 * 1024 * 1024:  # 500 MB limit
                self._send_json(413, {"success": False, "error": "File too large (> 500MB)"})
                return

            raw_body = self.rfile.read(content_length)
            fields, file_info = parse_multipart_form_data(raw_body, boundary)

            if not file_info:
                self._send_json(400, {"success": False, "error": "No file uploaded in form data"})
                return

            original_filename, file_bytes = file_info
            task = fields.get("task", "transcribe")  # "transcribe" or "translate"
            language = fields.get("language", "auto")
            model_name = fields.get("model", "large-v3-turbo")

            # Determine extension
            _, ext = os.path.splitext(original_filename)
            if not ext:
                ext = ".mp3"

            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp.write(file_bytes)
                    temp_path = tmp.name

                engine = get_web_engine(model_name)
                print(f"[WebStudio] Running {task} on '{original_filename}' ({len(file_bytes)} bytes) using {engine.model_name}...")

                result = engine.transcribe_file(
                    file_path=temp_path,
                    task=task,
                    language=None if language == "auto" else language,
                )

                result["filename"] = original_filename
                self._send_json(200, result)

            except Exception as e:
                print(f"[WebStudio] Processing error: {e}")
                self._send_json(500, {"success": False, "error": str(e)})
            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
            return

        self.send_error(404, "Endpoint not found")


def start_server(port: int = 8765, open_browser: bool = True):
    """Start the Friday Web Studio server."""
    os.makedirs(STATIC_DIR, exist_ok=True)
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, WebStudioHandler)
    url = f"http://127.0.0.1:{port}"

    print("==============================================================")
    print("   Friday Web Studio — Offline Audio Transcription & Translation")
    print("==============================================================")
    print(f"   Server URL:   {url}")
    print(f"   Acceleration: NVIDIA RTX 4060 GPU (CUDA float16)")
    print("   To Stop:      Press Ctrl+C in this console")
    print("==============================================================")

    if open_browser:
        def _open():
            time.sleep(1.0)
            import webbrowser
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[WebStudio] Stopping server...")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    port = 8765
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    start_server(port=port, open_browser=True)
