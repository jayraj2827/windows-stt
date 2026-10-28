"""
High-performance audio recorder using SoundDevice.
Captures 16kHz mono float32 audio for Faster-Whisper.
"""
import threading
from typing import Callable, List, Optional, Tuple
import numpy as np
import sounddevice as sd


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.stream: Optional[sd.InputStream] = None
        self.is_recording = False
        self.audio_chunks: List[np.ndarray] = []
        self._lock = threading.Lock()
        self.on_level_callback: Optional[Callable[[float], None]] = None
        # Dynamic auto-gain state
        self._peak_level = 0.015
        self._noise_floor = 0.0012

    @staticmethod
    def get_input_devices() -> List[Tuple[int, str, bool]]:
        """
        Enumerate all input audio devices.
        Returns list of (device_index, device_name, is_default).
        """
        devices = []
        try:
            device_list = sd.query_devices()
            default_input = sd.default.device[0]
            for idx, dev in enumerate(device_list):
                if dev.get("max_input_channels", 0) > 0:
                    is_default = (idx == default_input)
                    devices.append((idx, dev.get("name", f"Device {idx}"), is_default))
        except Exception as e:
            print(f"[AudioRecorder] Failed to list devices: {e}")
        return devices

    def set_level_callback(self, callback: Callable[[float], None]) -> None:
        """Register a callback for real-time RMS audio levels (0.0 to 1.0)."""
        self.on_level_callback = callback

    def _audio_callback(self, indata, frames, time_info, status):
        """Internal callback invoked by sounddevice for each chunk."""
        if status:
            print(f"[AudioRecorder] Stream status: {status}", flush=True)

        if not self.is_recording:
            return

        chunk = indata[:, 0].copy()  # Mono float32 array
        with self._lock:
            self.audio_chunks.append(chunk)

        # Calculate RMS amplitude with dynamic auto-gain normalization
        if self.on_level_callback:
            try:
                rms = float(np.sqrt(np.mean(chunk**2)))
                # Update rolling dynamic peak & floor
                if rms > self._peak_level:
                    self._peak_level = min(0.35, self._peak_level * 0.6 + rms * 0.4)
                else:
                    self._peak_level = max(0.008, self._peak_level * 0.97)

                # Normalized level between 0.0 and 1.0 with perceptual power curve
                val = max(0.0, rms - self._noise_floor) / max(0.005, self._peak_level - self._noise_floor)
                level = min(1.0, val) ** 0.65
                self.on_level_callback(level)
            except Exception:
                pass

    def start(self, device_index: Optional[int] = None) -> bool:
        """Start audio recording stream."""
        with self._lock:
            if self.is_recording:
                return True
            self.audio_chunks = []
            self.is_recording = True

        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                device=device_index,
                blocksize=1024,
                callback=self._audio_callback,
            )
            self.stream.start()
            return True
        except Exception as e:
            print(f"[AudioRecorder] Error starting stream: {e}")
            self.is_recording = False
            return False

    def stop(self) -> Optional[np.ndarray]:
        """
        Stop recording and return the accumulated audio as a float32 numpy array.
        Returns None if no audio or failed.
        """
        with self._lock:
            if not self.is_recording:
                return None
            self.is_recording = False

        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                print(f"[AudioRecorder] Error closing stream: {e}")
            finally:
                self.stream = None

        with self._lock:
            if not self.audio_chunks:
                return None
            audio_data = np.concatenate(self.audio_chunks, axis=0)
            self.audio_chunks = []

        # Reset level indicator
        if self.on_level_callback:
            self.on_level_callback(0.0)

        # Check if audio has sufficient length (at least ~0.2 seconds)
        if len(audio_data) < int(self.sample_rate * 0.2):
            return None

        return audio_data

