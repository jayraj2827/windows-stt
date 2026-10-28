"""
Faster-Whisper background worker with automatic CUDA detection and fallback.
"""
import os
import sys
import time
from typing import Any, Dict, Optional, Tuple
import numpy as np


def setup_cuda_dlls():
    """
    Ensure NVIDIA cuBLAS and cuDNN DLL directories are registered
    with Python's DLL loader and system PATH on Windows.
    """
    if sys.platform != "win32":
        return

    # Check site-packages for nvidia libraries
    site_packages = [p for p in sys.path if "site-packages" in p]
    for sp in site_packages:
        nvidia_dir = os.path.join(sp, "nvidia")
        if os.path.isdir(nvidia_dir):
            for sub in ["cublas", "cudnn"]:
                bin_dir = os.path.join(nvidia_dir, sub, "bin")
                if os.path.isdir(bin_dir):
                    try:
                        os.add_dll_directory(bin_dir)
                    except Exception:
                        pass
                    if bin_dir not in os.environ.get("PATH", ""):
                        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")


class WhisperEngine:
    def __init__(
        self,
        model_name: str = "small.en",
        device: str = "cuda",
        compute_type: str = "float16",
        language: str = "en",
        vad_filter: bool = True,
    ):
        self.model_name = model_name
        self.requested_device = device
        self.active_device = device
        self.compute_type = compute_type
        self.language = language if language != "auto" else None
        self.vad_filter = vad_filter
        self.model = None
        self.is_ready = False

    def load_model(self) -> Tuple[bool, str]:
        """
        Load the Faster-Whisper model into memory.
        Attempts CUDA first (if requested), falls back to CPU if unavailable.
        """
        setup_cuda_dlls()
        from faster_whisper import WhisperModel

        target_device = self.requested_device
        target_compute = self.compute_type

        # Attempt primary device (e.g. CUDA on RTX 4060)
        if target_device == "cuda":
            try:
                print(f"[WhisperEngine] Loading '{self.model_name}' on CUDA ({target_compute})...")
                self.model = WhisperModel(
                    self.model_name,
                    device="cuda",
                    compute_type=target_compute,
                )
                self.active_device = "cuda"
                self.is_ready = True
                msg = f"Model '{self.model_name}' loaded on NVIDIA CUDA ({target_compute})"
                print(f"[WhisperEngine] {msg}")
                return True, msg
            except Exception as e:
                print(f"[WhisperEngine] CUDA load failed ({e}). Falling back to CPU...")

        # Fallback to CPU
        try:
            print(f"[WhisperEngine] Loading '{self.model_name}' on CPU (int8)...")
            self.model = WhisperModel(
                self.model_name,
                device="cpu",
                compute_type="int8",
            )
            self.active_device = "cpu"
            self.is_ready = True
            msg = f"Model '{self.model_name}' loaded on CPU (int8 fallback)"
            print(f"[WhisperEngine] {msg}")
            return True, msg
        except Exception as e:
            self.is_ready = False
            msg = f"Failed to load Whisper model: {e}"
            print(f"[WhisperEngine] {msg}")
            return False, msg

    def transcribe(self, audio: np.ndarray) -> Dict[str, Any]:
        """
        Transcribe float32 16kHz audio array.
        Returns dict: {"text": str, "latency": float, "device": str, "language": str}
        """
        if not self.is_ready or self.model is None:
            return {"text": "", "error": "Model not loaded", "latency": 0.0}

        start_time = time.time()
        try:
            segments, info = self.model.transcribe(
                audio,
                language=self.language,
                beam_size=5,
                initial_prompt="Hello, this is clear English speech with precise punctuation, capitalization, numbers, and technical terminology.",
                condition_on_previous_text=False,
                temperature=[0.0, 0.2, 0.4],
                vad_filter=self.vad_filter,
                vad_parameters=dict(
                    min_silence_duration_ms=400,
                    speech_pad_ms=200,
                ),
            )

            text_parts = []
            for seg in segments:
                text_parts.append(seg.text)

            full_text = " ".join(text_parts).strip()
            latency = time.time() - start_time

            return {
                "text": full_text,
                "latency": round(latency, 3),
                "device": self.active_device,
                "language": info.language if info else self.language,
            }
        except Exception as e:
            print(f"[WhisperEngine] Transcription error: {e}")
            return {"text": "", "error": str(e), "latency": time.time() - start_time}

    def transcribe_streaming(self, audio: np.ndarray) -> str:
        """
        Progressive real-time streaming transcription pass.
        Optimized for minimal latency (beam_size=1, without timestamps).
        """
        if not self.is_ready or self.model is None or len(audio) < 4000:
            return ""

        try:
            segments, _ = self.model.transcribe(
                audio,
                language=self.language,
                beam_size=1,
                vad_filter=False,
                without_timestamps=True,
            )
            text_parts = [seg.text for seg in segments]
            return " ".join(text_parts).strip()
        except Exception:
            return ""

