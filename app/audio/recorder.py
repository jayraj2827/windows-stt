"""
High-performance audio recorder using SoundDevice.
Captures 16kHz mono float32 audio for Faster-Whisper.
Features ultra-low latency (32ms, blocksize 512), responsive 6-band FFT spectral decomposition,
and live streaming buffer snapshots for real-time progressive transcription.
"""
import threading
from typing import Callable, List, Optional, Tuple
import numpy as np
import sounddevice as sd


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, blocksize: int = 512):
        self.sample_rate = sample_rate
        self.blocksize = blocksize
        self.stream: Optional[sd.InputStream] = None
        self.is_recording = False
        self.audio_chunks: List[np.ndarray] = []
        self._lock = threading.Lock()

        # Callbacks
        self.on_level_callback: Optional[Callable[[float], None]] = None
        self.on_bands_callback: Optional[Callable[[List[float]], None]] = None

        # Precompute Hanning window and FFT frequency bins
        self._hanning = np.hanning(self.blocksize).astype(np.float32)
        freqs = np.fft.rfftfreq(self.blocksize, 1.0 / self.sample_rate)

        # 6 spectral bands: (low_freq, high_freq)
        bands_def = [
            (100, 350),    # Band 0: Deep vocal fundamentals / pitch
            (350, 750),    # Band 1: Lower mid / vowel body
            (750, 1500),   # Band 2: Mid vocal resonance / formants
            (1500, 2800),  # Band 3: Upper mid / articulation
            (2800, 5000),  # Band 4: Consonants / sibilance ('s', 't', 'ch')
            (5000, 7800),  # Band 5: Treble crispness / breath
        ]
        self._band_slices = []
        for low, high in bands_def:
            idx = np.where((freqs >= low) & (freqs < high))[0]
            if len(idx) > 0:
                self._band_slices.append((idx[0], idx[-1] + 1))
            else:
                self._band_slices.append((0, 1))

        # Dynamic auto-gain state per band (responsive to real mic volume)
        self._band_floors = [0.0001] * len(self._band_slices)
        self._band_peaks = [0.002] * len(self._band_slices)
        self._peak_rms = 0.003
        self._floor_rms = 0.00015

    @staticmethod
    def get_input_devices() -> List[Tuple[int, str, bool]]:
        """
        Enumerate genuine microphone input devices.
        Filters out loopback speakers (Stereo Mix, PC Speaker, etc.) and legacy MME wrappers.
        Prioritizes Windows WASAPI for bit-exact, lowest latency, highest Whisper accuracy.
        """
        devices = []
        try:
            device_list = sd.query_devices()
            hostapis = sd.query_hostapis()

            for idx, dev in enumerate(device_list):
                if dev.get("max_input_channels", 0) <= 0:
                    continue

                name = dev.get("name", f"Device {idx}")
                name_lower = name.lower()

                # Filter out audio loopback and speaker output devices
                if any(bad in name_lower for bad in [
                    "speaker", "stereo mix", "sound mapper", "primary sound capture",
                    "line out", "output", "wave out", "mapper"
                ]):
                    continue

                api_id = dev.get("hostapi", 0)
                api_name = hostapis[api_id]["name"] if api_id < len(hostapis) else ""
                is_wasapi = "wasapi" in api_name.lower()

                if is_wasapi:
                    label = f"[RECOMMENDED] {name} — WASAPI (Highest Accuracy)"
                else:
                    label = f"{name} ({api_name})"

                devices.append((idx, label, is_wasapi))

            # Sort: WASAPI / Recommended at the top
            devices.sort(key=lambda x: (not x[2], x[0]))

        except Exception as e:
            print(f"[AudioRecorder] Failed to list devices: {e}")
        return devices

    def set_level_callback(self, callback: Callable[[float], None]) -> None:
        """Register a callback for overall RMS audio level (0.0 to 1.0)."""
        self.on_level_callback = callback

    def set_bands_callback(self, callback: Callable[[List[float]], None]) -> None:
        """Register a callback for 6-band FFT normalized frequency spectrum."""
        self.on_bands_callback = callback

    def _audio_callback(self, indata, frames, time_info, status):
        """Ultra-low latency audio processing callback (32ms)."""
        if not self.is_recording:
            return

        chunk = indata[:, 0].copy()  # Mono float32 array
        with self._lock:
            self.audio_chunks.append(chunk)

        # 1. Overall RMS calculation
        rms = float(np.sqrt(np.mean(chunk**2)))
        if rms < self._floor_rms * 1.5:
            self._floor_rms = self._floor_rms * 0.9 + rms * 0.1
        clean_rms = max(0.0, rms - self._floor_rms)

        if clean_rms > self._peak_rms:
            self._peak_rms = min(0.1, self._peak_rms * 0.5 + clean_rms * 0.5)
        else:
            self._peak_rms = max(0.001, self._peak_rms * 0.97)

        norm_level = min(1.0, (clean_rms / self._peak_rms) ** 0.55)

        if self.on_level_callback:
            try:
                self.on_level_callback(norm_level)
            except Exception:
                pass

        # 2. Fast 6-Band FFT Spectral Decomposition (Real Voice Sync)
        if self.on_bands_callback:
            try:
                windowed = chunk * self._hanning
                fft_vals = np.abs(np.fft.rfft(windowed))

                band_levels = []
                for i, (start_idx, end_idx) in enumerate(self._band_slices):
                    energy = float(np.mean(fft_vals[start_idx:end_idx]))

                    # Dynamically track noise floor for this band
                    if energy < self._band_floors[i] * 1.6:
                        self._band_floors[i] = self._band_floors[i] * 0.92 + energy * 0.08

                    sig = max(0.0, energy - self._band_floors[i])

                    # Dynamically track peak voice energy for this band
                    if sig > self._band_peaks[i]:
                        self._band_peaks[i] = min(0.1, self._band_peaks[i] * 0.5 + sig * 0.5)
                    else:
                        self._band_peaks[i] = max(0.0008, self._band_peaks[i] * 0.96)

                    # Dynamic normalized level (0.0 = total silence, 1.0 = peak spoken syllable)
                    norm_energy = min(1.0, (sig / self._band_peaks[i]) ** 0.55)
                    band_levels.append(norm_energy)

                self.on_bands_callback(band_levels)
            except Exception:
                pass

    def get_current_audio_copy(self) -> Optional[np.ndarray]:
        """
        Thread-safe snapshot of currently recorded audio so far.
        Enables progressive real-time streaming speech-to-text without interrupting recording.
        """
        with self._lock:
            if not self.is_recording or not self.audio_chunks:
                return None
            return np.concatenate(self.audio_chunks, axis=0)

    def start(self, device_index: Optional[int] = None) -> bool:
        """Start low-latency audio recording stream."""
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
                blocksize=self.blocksize,
                callback=self._audio_callback,
            )
            self.stream.start()
            return True
        except Exception as e:
            print(f"[AudioRecorder] Error starting stream: {e}")
            self.is_recording = False
            return False

    def stop(self) -> Optional[np.ndarray]:
        """Stop recording and return the accumulated audio as a float32 array."""
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

        # Reset visualizers
        if self.on_level_callback:
            self.on_level_callback(0.0)
        if self.on_bands_callback:
            self.on_bands_callback([0.0] * len(self._band_slices))

        if len(audio_data) < int(self.sample_rate * 0.2):
            return None

        return audio_data
