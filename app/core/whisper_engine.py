"""
Unified Faster-Whisper Engine for Friday STT & Web Studio.
Hardware-accelerated via NVIDIA CUDA (float16) on RTX 4060 GPU with CPU int8 fallback.
Supports:
- Real-time microphone buffer transcription (low latency, beam_size=5)
- Real-time streaming transcription (beam_size=1, progressive preview)
- Full audio/video file transcription and translation (mp3, wav, m4a, mp4, flac, etc.)
- Offline speech translation (translates 99+ languages into English text)
"""
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


def setup_cuda_dlls():
    """Register NVIDIA cuBLAS and cuDNN Windows DLLs with Python DLL loader and system PATH."""
    if sys.platform != "win32":
        return

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
        model_name: str = "large-v3-turbo",
        device: str = "cuda",
        compute_type: str = "float16",
        language: Optional[str] = "en",
        vad_filter: bool = True,
    ):
        self.model_name = model_name
        self.requested_device = device
        self.active_device = device
        self.compute_type = compute_type
        self.language = language if (language and language != "auto") else None
        self.vad_filter = vad_filter
        self.model = None
        self.is_ready = False
        self._lock = threading.Lock()

    def load_model(self, model_name: Optional[str] = None) -> Tuple[bool, str]:
        """Load Faster-Whisper weights into GPU/CPU memory."""
        if model_name:
            self.model_name = model_name

        setup_cuda_dlls()
        from faster_whisper import WhisperModel

        target_device = self.requested_device
        target_compute = self.compute_type

        # 1. Attempt CUDA on RTX 4060
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

        # 2. CPU int8 Fallback
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
        """Transcribe microphone float32 audio buffer for desktop real-time STT."""
        if not self.is_ready or self.model is None or len(audio) < 1600:
            return {"text": "", "error": "No audio" if len(audio) < 1600 else "Model not loaded", "latency": 0.0}

        # Fast silence check to prevent Whisper from hallucinating on dead air
        peak = float(np.max(np.abs(audio)))
        if peak < 0.02:
            return {"text": "", "latency": 0.0, "device": self.active_device, "language": self.language}

        start_time = time.time()
        with self._lock:
            try:
                segments, info = self.model.transcribe(
                    audio,
                    language=self.language,
                    beam_size=5,
                    temperature=0.0,
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=500,
                        speech_pad_ms=400,
                        threshold=0.30,
                    ),
                )

                HALLUCINATIONS = {"you", "you.", "thank you", "thank you.", "subtitles by", "bye", "bye."}

                text_parts = []
                for seg in segments:
                    clean = seg.text.strip()
                    if clean.lower() in HALLUCINATIONS and seg.no_speech_prob > 0.30:
                        continue
                    if seg.no_speech_prob > 0.70:
                        continue
                    if clean:
                        text_parts.append(clean)

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
        """Fast greedy streaming transcription for floating overlay live preview."""
        if not self.is_ready or self.model is None or len(audio) < 4000:
            return ""

        peak = float(np.max(np.abs(audio)))
        if peak < 0.02:
            return ""

        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            return ""

        try:
            segments, _ = self.model.transcribe(
                audio,
                language=self.language,
                beam_size=1,
                temperature=0.0,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=350,
                    threshold=0.30,
                ),
                without_timestamps=True,
            )

            HALLUCINATIONS = {"you", "you.", "thank you", "thank you.", "subtitles by"}
            text_parts = []
            for seg in segments:
                clean = seg.text.strip()
                if clean.lower() in HALLUCINATIONS and seg.no_speech_prob > 0.30:
                    continue
                if clean:
                    text_parts.append(clean)

            return " ".join(text_parts).strip()
        except Exception:
            return ""
        finally:
            self._lock.release()

    def transcribe_file(
        self,
        file_path: str,
        task: str = "transcribe",  # "transcribe" (original language) or "translate" (offline to English)
        language: Optional[str] = None,
        beam_size: int = 5,
    ) -> Dict[str, Any]:
        """
        Transcribe or translate an audio/video file for Web Studio.
        Accepts mp3, wav, m4a, mp4, flac, ogg, webm, aac, etc.
        Returns complete segments with timestamps, full text, duration, and latency.
        """
        if not self.is_ready or self.model is None:
            return {"success": False, "error": "Model not loaded"}

        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        start_time = time.time()
        target_lang = language if (language and language != "auto") else None

        with self._lock:
            try:
                segments_gen, info = self.model.transcribe(
                    file_path,
                    task=task,
                    language=target_lang,
                    beam_size=beam_size,
                    vad_filter=True,
                    vad_parameters=dict(
                        min_silence_duration_ms=400,
                        speech_pad_ms=300,
                        threshold=0.30,
                    ),
                )

                segments_list = []
                full_text_parts = []

                for seg in segments_gen:
                    clean_text = seg.text.strip()
                    if not clean_text:
                        continue
                    item = {
                        "id": seg.id,
                        "start": round(seg.start, 2),
                        "end": round(seg.end, 2),
                        "text": clean_text,
                        "no_speech_prob": round(seg.no_speech_prob, 3),
                    }
                    segments_list.append(item)
                    full_text_parts.append(clean_text)

                latency = round(time.time() - start_time, 2)
                full_text = " ".join(full_text_parts).strip()

                return {
                    "success": True,
                    "task": task,
                    "text": full_text,
                    "language": info.language if info else target_lang,
                    "language_probability": round(info.language_probability, 3) if info else 1.0,
                    "duration": round(info.duration, 2) if info else 0.0,
                    "latency": latency,
                    "segments": segments_list,
                    "model": self.model_name,
                    "device": self.active_device,
                }
            except Exception as e:
                print(f"[WhisperEngine] File {task} error: {e}")
                return {"success": False, "error": str(e), "latency": round(time.time() - start_time, 2)}
