"""
Backward-compatibility wrapper for app.engine.whisper_worker.
Redirects to app.core.whisper_engine.
"""
from app.core.whisper_engine import WhisperEngine, setup_cuda_dlls

__all__ = ["WhisperEngine", "setup_cuda_dlls"]
