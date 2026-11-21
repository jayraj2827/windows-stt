"""
Friday Web Studio — FastAPI Backend.
High-performance, local, privacy-first web application for audio/video transcription and translation.
Powered by NVIDIA RTX 4060 GPU (CUDA float16) via Faster-Whisper.
Runs on http://127.0.0.1:8765
"""
import os
import sys
import tempfile
import threading
import time
import webbrowser
from typing import Any, Dict, List, Optional

import pyperclip
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app.core.formatters import segments_to_srt, segments_to_txt, segments_to_vtt
from app.core.whisper_engine import WhisperEngine
from app.core.translator import get_translator, SUPPORTED_LANGUAGES

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
HTML_FILE = os.path.join(STATIC_DIR, "index.html")

# Global engine instance for Web Studio
_engine_lock = threading.Lock()
_global_engine: Optional[WhisperEngine] = None


def set_shared_engine(engine: WhisperEngine):
    """Register an already initialized WhisperEngine from Desktop Assistant."""
    global _global_engine
    with _engine_lock:
        _global_engine = engine
        print(f"[FastAPI WebStudio] Linked shared WhisperEngine '{engine.model_name}' on {engine.active_device} from Desktop Assistant.")


def get_web_engine(model_name: str = "large-v3-turbo") -> WhisperEngine:
    """
    Retrieve or initialize the shared Whisper engine for Web Studio.
    If already loaded by Desktop Assistant or Web Studio, reuses the active model instance.
    """
    global _global_engine
    with _engine_lock:
        if _global_engine is not None and _global_engine.is_ready and _global_engine.model is not None:
            # Checkpoint: reuse existing engine if requested model is the same
            if model_name and _global_engine.model_name != model_name:
                print(f"[FastAPI WebStudio] Switching engine model from {_global_engine.model_name} to {model_name}...")
                _global_engine.load_model(model_name)
            return _global_engine

        # If not already initialized, create and load
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
            print(f"[FastAPI WebStudio] Switching engine model from {_global_engine.model_name} to {model_name}...")
            _global_engine.load_model(model_name)
        return _global_engine


# Pydantic Request Models
class CopyRequest(BaseModel):
    text: str


class ExportRequest(BaseModel):
    segments: List[Dict[str, Any]] = []
    format: str = "txt"  # "txt", "srt", "vtt"
    filename: str = "transcript"


class TextTranslateRequest(BaseModel):
    text: str
    source_lang: str = "auto"
    target_lang: str = "hin_Deva"


# FastAPI Application Instance
app = FastAPI(
    title="Friday AI Web Studio",
    description="Offline Speech-to-Text & Neural Audio Translation powered by NVIDIA CUDA",
    version="2.0.0",
)

# Enable CORS for local origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=FileResponse)
async def serve_index():
    """Serve the primary Friday Studio single-page application."""
    if not os.path.exists(HTML_FILE):
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(HTML_FILE, media_type="text/html")


@app.get("/favicon.ico")
async def favicon():
    """Handle browser favicon requests gracefully."""
    return Response(status_code=204)


@app.get("/api/languages")
async def get_languages():
    """Return list of supported translation languages."""
    return {"languages": SUPPORTED_LANGUAGES}


@app.post("/api/translate")
async def translate_text(payload: TextTranslateRequest):
    """
    Translate text using local Meta NLLB-200 on RTX 4060 GPU (CUDA float16).
    """
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="No text provided for translation.")

    translator = get_translator()
    result = translator.translate(
        text=payload.text,
        source_lang=payload.source_lang,
        target_lang=payload.target_lang,
    )
    if not result.get("success", False):
        raise HTTPException(status_code=500, detail=result.get("error", "Translation failed"))
    return result


@app.get("/api/status")
async def get_status():
    """Query current GPU acceleration status, loaded Whisper model, and NLLB translator."""
    engine = get_web_engine()
    return {
        "status": "ready" if engine.is_ready else "loading",
        "model": engine.model_name,
        "device": engine.active_device,
        "compute_type": engine.compute_type,
        "gpu_name": "NVIDIA GeForce RTX 4060 Laptop GPU",
        "supported_models": [
            "large-v3-turbo",
            "large-v3",
            "medium",
            "small",
            "base",
            "tiny",
        ],
    }


@app.post("/api/transcribe")
async def transcribe_media(
    file: UploadFile = File(...),
    task: str = Form("transcribe"),  # "transcribe" or "translate"
    model: str = Form("large-v3-turbo"),
    language: str = Form("auto"),
):
    """
    Transcribe or translate an uploaded audio/video file using Faster-Whisper on RTX 4060.
    Accepts MP3, WAV, M4A, MP4, FLAC, OGG, WEBM, AAC.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    _, ext = os.path.splitext(file.filename)
    if not ext:
        ext = ".mp3"

    temp_path = None
    try:
        # Stream uploaded chunks to temporary file
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            temp_path = tmp.name
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                tmp.write(chunk)

        engine = get_web_engine(model)
        print(f"[FastAPI WebStudio] Processing '{file.filename}' ({task}) using model '{engine.model_name}' on {engine.active_device}...")

        result = engine.transcribe_file(
            file_path=temp_path,
            task=task,
            language=None if language == "auto" else language,
        )

        result["filename"] = file.filename
        return result

    except Exception as e:
        print(f"[FastAPI WebStudio] Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.post("/api/copy")
async def copy_to_clipboard(payload: CopyRequest):
    """Safely copy text into the Windows host clipboard."""
    if not payload.text:
        raise HTTPException(status_code=400, detail="No text provided")
    try:
        pyperclip.copy(payload.text)
        return {"success": True, "message": "Copied to clipboard"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clipboard error: {e}")


@app.post("/api/export")
async def export_transcript(payload: ExportRequest):
    """Export segments into formatted TXT, SRT, or VTT files."""
    fmt = payload.format.lower()
    base_name = payload.filename or "transcript"

    if fmt == "srt":
        content = segments_to_srt(payload.segments)
        ext = "srt"
        mime = "text/plain; charset=utf-8"
    elif fmt == "vtt":
        content = segments_to_vtt(payload.segments)
        ext = "vtt"
        mime = "text/vtt; charset=utf-8"
    else:
        content = segments_to_txt(payload.segments)
        ext = "txt"
        mime = "text/plain; charset=utf-8"

    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{base_name}.{ext}"'},
    )


def start_server(port: int = 8765, open_browser: bool = True):
    """Start the Friday Web Studio via Uvicorn."""
    os.makedirs(STATIC_DIR, exist_ok=True)
    url = f"http://127.0.0.1:{port}"

    print("==============================================================")
    print("   Friday Web Studio (FastAPI) — Local AI Studio")
    print("==============================================================")
    print(f"   Framework:    FastAPI + Uvicorn")
    print(f"   Server URL:   {url}")
    print(f"   API Docs:     {url}/docs")
    print(f"   Acceleration: NVIDIA RTX 4060 GPU (CUDA float16)")
    print("   To Stop:      Press Ctrl+C in this console")
    print("==============================================================")

    if open_browser:
        def _open():
            time.sleep(1.2)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    port = 8765
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    start_server(port=port, open_browser=True)
