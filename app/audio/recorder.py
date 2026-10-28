"""
Adaptive audio recorder using SoundDevice.
Supports 16kHz direct capture as well as high-res 48kHz Windows WASAPI native capture
with studio-grade automatic downsampling to 16kHz for Faster-Whisper.
Features responsive 6-band FFT spectral decomposition and progressive streaming snapshots.
"""
import threading
from typing import Callable, List, Optional, Tuple
import numpy as np
import scipy.signal
import sounddevice as sd


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, target_sample_rate: Optional[int] = None, **kwargs):
        self.target_sample_rate = target_sample_rate if target_sample_rate is not None else sample_rate
        self.sample_rate = self.target_sample_rate
        self.active_sample_rate = self.target_sample_rate
        self.blocksize = 512
        self.stream: Optional[sd.InputStream] = None
        self.is_recording = False
        self.audio_chunks: List[np.ndarray] = []
        self._lock = threading.Lock()

        # Callbacks
        self.on_level_callback: Optional[Callable[[float], None]] = None
        self.on_bands_callback: Optional[Callable[[List[float]], None]] = None

        # Spectral analyzer state
        self._hanning = None
        self._band_slices = []
        self._band_floors = [0.0001] * 6
        self._band_peaks = [0.002] * 6
        self._peak_rms = 0.003
        self._floor_rms = 0.00015

        self._configure_spectral_analyzer(16000, 512)

    def _configure_spectral_analyzer(self, sample_rate: int, blocksize: int):
        """Configure Hanning window and 6 frequency bands for active sample rate."""
        self._hanning = np.hanning(blocksize).astype(np.float32)
        freqs = np.fft.rfftfreq(blocksize, 1.0 / sample_rate)

        bands_def = [
            (100, 350),    # Band 0: Deep vocal fundamentals
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

    @staticmethod
    def get_input_devices() -> List[Tuple[Optional[int], str, bool]]:
        """
        Enumerate genuine microphone input devices.
        Filters out loopback speakers (Stereo Mix, PC Speaker, etc.).
        Prioritizes Windows WASAPI for lowest latency and highest accuracy.
        """
        devices = []
        # Add system default as top general option
        devices.append((None, "Windows Default Audio Input", False))

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
                    label = f"[RECOMMENDED] {name} - WASAPI (Highest Accuracy)"
                else:
                    label = f"{name} ({api_name})"

                devices.append((idx, label, is_wasapi))

            # Keep Default at top, then WASAPI, then others
            devices.sort(key=lambda x: (x[0] is not None, not x[2]))

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
        """Audio streaming callback."""
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

        # 2. Fast 6-Band FFT Spectral Decomposition (Syllable Sync)
        if self.on_bands_callback and self._hanning is not None:
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

                    norm_energy = min(1.0, (sig / self._band_peaks[i]) ** 0.55)
                    band_levels.append(norm_energy)

                self.on_bands_callback(band_levels)
            except Exception:
                pass

    def _resample_to_16k(self, audio_data: np.ndarray) -> np.ndarray:
        """Resample audio data to 16000 Hz if recorded at another sample rate."""
        if self.active_sample_rate == 16000 or len(audio_data) == 0:
            return audio_data

        if self.active_sample_rate == 48000:
            # Exact 3:1 integer downsampling with studio anti-aliasing
            return scipy.signal.resample_poly(audio_data, 1, 3).astype(np.float32)
        else:
            # Arbitrary resampling
            target_len = int(len(audio_data) * 16000 / self.active_sample_rate)
            return scipy.signal.resample(audio_data, target_len).astype(np.float32)

    def get_current_audio_copy(self) -> Optional[np.ndarray]:
        """
        Thread-safe snapshot of currently recorded audio resampled to 16kHz.
        Enables progressive real-time streaming speech-to-text without interrupting recording.
        """
        with self._lock:
            if not self.is_recording or not self.audio_chunks:
                return None
            raw = np.concatenate(self.audio_chunks, axis=0)

        return self._resample_to_16k(raw)

    def start(self, device_index: Optional[int] = None) -> bool:
        """
        Start audio recording stream.
        Attempts 16kHz directly, automatically falls back to native device rate (e.g. 48kHz WASAPI).
        """
        with self._lock:
            if self.is_recording:
                return True
            self.audio_chunks = []
            self.is_recording = True

        # Query native rate for fallback
        try:
            if device_index is not None:
                dev_info = sd.query_devices(device_index)
            else:
                dev_info = sd.query_devices(sd.default.device[0])
            native_rate = int(dev_info.get("default_samplerate", 48000))
        except Exception:
            native_rate = 48000

        # Try target rate (16000) first
        opened = False
        for rate in [16000, native_rate, 48000, 44100]:
            try:
                # 32ms block size
                block = int(rate * 0.032)
                self.stream = sd.InputStream(
                    samplerate=rate,
                    channels=1,
                    dtype="float32",
                    device=device_index,
                    blocksize=block,
                    callback=self._audio_callback,
                )
                self.stream.start()
                self.active_sample_rate = rate
                self.blocksize = block
                self._configure_spectral_analyzer(rate, block)
                opened = True
                break
            except Exception:
                continue

        if not opened and device_index is not None:
            print(f"[AudioRecorder] Device {device_index} failed, falling back to system default input...")
            for rate in [16000, 48000, 44100]:
                try:
                    block = int(rate * 0.032)
                    self.stream = sd.InputStream(
                        samplerate=rate,
                        channels=1,
                        dtype="float32",
                        device=None,
                        blocksize=block,
                        callback=self._audio_callback,
                    )
                    self.stream.start()
                    self.active_sample_rate = rate
                    self.blocksize = block
                    self._configure_spectral_analyzer(rate, block)
                    opened = True
                    break
                except Exception:
                    continue

        if not opened:
            print(f"[AudioRecorder] Failed to open audio input on device {device_index} and fallback")
            self.is_recording = False
            return False

        return True

    def stop(self) -> Optional[np.ndarray]:
        """Stop recording and return 16kHz float32 audio array."""
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
            raw = np.concatenate(self.audio_chunks, axis=0)
            self.audio_chunks = []

        # Reset visualizers
        if self.on_level_callback:
            self.on_level_callback(0.0)
        if self.on_bands_callback:
            self.on_bands_callback([0.0] * 6)

        audio_16k = self._resample_to_16k(raw)

        if len(audio_16k) < int(self.target_sample_rate * 0.2):
            return None

        return audio_16k
