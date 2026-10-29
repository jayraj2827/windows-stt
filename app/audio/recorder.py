"""
Adaptive audio recorder using SoundDevice.
Supports 16kHz direct capture as well as high-res 48kHz Windows WASAPI native capture
with studio-grade automatic downsampling to 16kHz for Faster-Whisper.
Features responsive 6-band FFT spectral decomposition and progressive streaming snapshots.
"""
import collections
import threading
from typing import Callable, List, Optional, Tuple
import numpy as np
import scipy.signal
import sounddevice as sd


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, target_sample_rate: Optional[int] = None, mic_mode: str = "on_demand", **kwargs):
        self.target_sample_rate = target_sample_rate if target_sample_rate is not None else sample_rate
        self.sample_rate = self.target_sample_rate
        self.active_sample_rate = self.target_sample_rate
        self.mic_mode = mic_mode  # "on_demand" (open only while pressing key) or "always_ready"
        self.blocksize = 512
        self.stream: Optional[sd.InputStream] = None
        self.active_device_index: Optional[int] = None
        self.is_recording = False
        self.audio_chunks: List[np.ndarray] = []
        # Pre-roll ring buffer (~448ms) used in always_ready mode
        self.preroll_buffer: collections.deque = collections.deque(maxlen=14)
        self._cached_rates = {}
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
        """Audio streaming callback running continuously in background."""
        chunk = indata[:, 0].copy()  # Mono float32 array
        with self._lock:
            if self.is_recording:
                self.audio_chunks.append(chunk)
            else:
                self.preroll_buffer.append(chunk)

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

        # 2. Dynamic 6-Band FFT Spectral Decomposition (True Syllable & Phoneme Sync)
        if self.on_bands_callback and self._hanning is not None:
            try:
                # If silent or room ambient noise, immediately output resting silence
                if clean_rms < 0.0008:
                    self.on_bands_callback([0.0] * 6)
                else:
                    windowed = chunk * self._hanning
                    fft_vals = np.abs(np.fft.rfft(windowed))

                    # Speech acoustic weighting: balances human vocal fundamentals with treble sibilance
                    weights = [0.85, 1.0, 1.15, 1.35, 1.6, 1.9]
                    band_levels = []

                    # Shared vocal energy reference (prevents clipping all bars into a flat wall)
                    ref_peak = max(0.008, self._peak_rms * 2.8)

                    for i, (start_idx, end_idx) in enumerate(self._band_slices):
                        energy = float(np.mean(fft_vals[start_idx:end_idx]))

                        # Track background floor per band
                        if energy < self._band_floors[i] * 1.5:
                            self._band_floors[i] = self._band_floors[i] * 0.94 + energy * 0.06

                        sig = max(0.0, energy - self._band_floors[i])
                        weighted_sig = sig * weights[i]

                        # Log-scaled response matching human acoustic perception
                        norm_energy = min(1.0, (weighted_sig / ref_peak) ** 0.65)
                        band_levels.append(norm_energy)

                    self.on_bands_callback(band_levels)
            except Exception:
                pass

    def _resample_to_16k(self, audio_data: np.ndarray) -> np.ndarray:
        """Resample audio data to 16000 Hz if recorded at another sample rate, and apply intelligent AGC."""
        if len(audio_data) == 0:
            return audio_data

        if self.active_sample_rate == 48000:
            # Exact 3:1 integer downsampling with studio anti-aliasing
            audio_16k = scipy.signal.resample_poly(audio_data, 1, 3).astype(np.float32)
        elif self.active_sample_rate != 16000:
            # Arbitrary resampling
            target_len = int(len(audio_data) * 16000 / self.active_sample_rate)
            audio_16k = scipy.signal.resample(audio_data, target_len).astype(np.float32)
        else:
            audio_16k = audio_data.astype(np.float32)

        # Intelligent Speech Normalization (AGC):
        # Laptop mic arrays on Windows WASAPI often record at -35dB (peak ~0.008).
        # Normalizing peak amplitude to 0.70 ensures Whisper's acoustic encoder
        # receives pristine, nominal audio rather than confusing speech with background noise!
        peak = float(np.max(np.abs(audio_16k)))
        if peak > 0.002:
            scale = min(25.0, 0.70 / peak)
            audio_16k = audio_16k * scale

        return np.clip(audio_16k, -1.0, 1.0)

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

    def _ensure_stream_open(self, device_index: Optional[int] = None) -> bool:
        """
        Open the PortAudio stream if not yet open or if device changed.
        Uses cached native sample rate first for sub-50ms instant opening.
        """
        if self.stream is not None and self.stream.active and self.active_device_index == device_index:
            return True

        if self.stream is not None:
            self.close()

        # Query native rate for device
        try:
            if device_index is not None:
                dev_info = sd.query_devices(device_index)
            else:
                dev_info = sd.query_devices(sd.default.device[0])
            native_rate = int(dev_info.get("default_samplerate", 48000))
        except Exception:
            native_rate = 48000

        # Prioritize cached rate or native hardware rate first (e.g. 48000/44100)
        cached_rate = self._cached_rates.get(device_index)
        rates_to_try = [cached_rate] if cached_rate else []
        for r in [native_rate, 48000, 44100, 16000]:
            if r not in rates_to_try:
                rates_to_try.append(r)

        opened = False
        for rate in rates_to_try:
            try:
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
                self.active_device_index = device_index
                self._cached_rates[device_index] = rate
                self._configure_spectral_analyzer(rate, block)
                opened = True
                break
            except Exception:
                continue

        # Fallback to system default device if specified device failed
        if not opened and device_index is not None:
            print(f"[AudioRecorder] Device {device_index} failed, falling back to system default...")
            for rate in [48000, 44100, 16000]:
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
                    self.active_device_index = None
                    self._configure_spectral_analyzer(rate, block)
                    opened = True
                    break
                except Exception:
                    continue

        return opened

    def start(self, device_index: Optional[int] = None) -> bool:
        """
        Start audio recording stream on hotkey press.
        In on_demand mode (default), opens the microphone stream immediately on key press.
        """
        with self._lock:
            self.audio_chunks = []
            self.is_recording = True

        opened = self._ensure_stream_open(device_index)
        if not opened:
            with self._lock:
                self.is_recording = False
            return False

        # In always_ready mode, prepend pre-roll buffer if available
        if self.mic_mode == "always_ready":
            with self._lock:
                self.audio_chunks = list(self.preroll_buffer)
                self.preroll_buffer.clear()

        return True

    def stop(self) -> Optional[np.ndarray]:
        """
        Stop recording and return 16kHz float32 audio array.
        In on_demand mode (default), immediately closes and releases the microphone hardware!
        """
        with self._lock:
            if not self.is_recording:
                return None
            self.is_recording = False

            if not self.audio_chunks:
                raw = np.array([], dtype=np.float32)
            else:
                raw = np.concatenate(self.audio_chunks, axis=0)
            self.audio_chunks = []

        # If on_demand mode, immediately close and release microphone stream
        # so Windows microphone indicator icon disappears and mic is completely released!
        if self.mic_mode == "on_demand":
            self.close()

        # Reset visualizers to clean resting state
        if self.on_level_callback:
            self.on_level_callback(0.0)
        if self.on_bands_callback:
            self.on_bands_callback([0.0] * 6)

        if len(raw) == 0:
            return None

        audio_16k = self._resample_to_16k(raw)
        if len(audio_16k) < int(self.target_sample_rate * 0.15):  # Min 150ms
            return None

        return audio_16k

    def close(self):
        """Cleanly close underlying PortAudio stream on exit."""
        with self._lock:
            self.is_recording = False
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            finally:
                self.stream = None
