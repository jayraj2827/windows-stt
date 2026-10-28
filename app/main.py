"""
Main application coordinator for Windows STT Subsystem.
Integrates Audio Recorder, Whisper Engine, Global Hotkeys, Floating Overlay, and Settings Hub.
Includes Single-Instance enforcement, Windows Process ID tracking, and named application identity.
"""
import atexit
import ctypes
import os
import sys
import threading
from typing import Any, Dict, Optional
import numpy as np
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMessageBox

from app.audio.recorder import AudioRecorder
from app.config import load_config, save_config
from app.engine.injector import TextInjector
from app.engine.whisper_worker import WhisperEngine
from app.hotkeys.listener import HotkeyListener
from app.ui.overlay import FloatingOverlay
from app.ui.settings_window import SettingsWindow
from app.ui.tray import TrayManager

PID_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".stt.pid")
MUTEX_NAME = "Global\\WindowsSTT_VoiceTyping_SingleInstance"


def ensure_single_instance():
    """Ensure only one instance runs at a time via Windows named mutex."""
    if sys.platform != "win32":
        return None
    try:
        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
        ERROR_ALREADY_EXISTS = 183
        if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            return None
        return mutex
    except Exception as e:
        print(f"[Windows STT] Mutex warning: {e}")
        return None


def register_pid():
    """Save current process PID for stop.bat."""
    try:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass


def cleanup_pid():
    """Remove PID file on clean exit."""
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
    except Exception:
        pass


class AppCoordinator(QObject):
    sig_start_recording = pyqtSignal(str)
    sig_stop_recording = pyqtSignal(str)
    sig_transcription_finished = pyqtSignal(str, float)
    sig_model_status = pyqtSignal(bool, str)

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config

        # 1. Initialize Subsystems
        self.recorder = AudioRecorder(sample_rate=16000)
        self.injector = TextInjector(
            method=self.config.get("injection_method", "clipboard"),
            restore_clipboard=self.config.get("restore_clipboard", True),
        )
        self.whisper_engine = WhisperEngine(
            model_name=self.config.get("model_name", "small.en"),
            device=self.config.get("device", "cuda"),
            compute_type=self.config.get("compute_type", "float16"),
            language=self.config.get("language", "en"),
            vad_filter=self.config.get("vad_filter", True),
        )

        # 2. UI Components
        self.overlay = FloatingOverlay()
        self.settings_window = SettingsWindow(self.config)
        self.tray = TrayManager(current_model=self.config.get("model_name", "small.en"))

        # Connect audio level to overlay waveform
        self.recorder.set_level_callback(lambda lvl: self.overlay.sig_audio_level.emit(lvl))

        # 3. Hotkey Listener
        self.hotkeys = HotkeyListener(
            hotkey_hold_str=self.config.get("hotkey_hold", "<ctrl>+<space>"),
            hotkey_toggle_str=self.config.get("hotkey_toggle", "<ctrl>+<shift>+<space>"),
            on_start_record=self._on_hotkey_start_record,
            on_stop_record=self._on_hotkey_stop_record,
        )

        # 4. Connect Signals
        self._wire_signals()

        # 5. Start Background Model Loader & Hotkeys
        self._start_initialization()

    def _wire_signals(self):
        self.sig_start_recording.connect(self._handle_start_recording)
        self.sig_stop_recording.connect(self._handle_stop_recording)
        self.sig_transcription_finished.connect(self._handle_transcription_finished)

        self.settings_window.sig_settings_changed.connect(self._on_settings_updated)
        self.settings_window.sig_reload_model_requested.connect(self._reload_model)

        self.tray.sig_open_settings.connect(self._show_settings)
        self.tray.sig_toggle_recording.connect(self._toggle_recording_manual)
        self.tray.sig_switch_model.connect(self._reload_model)
        self.tray.sig_exit.connect(self._exit_app)

    def _start_initialization(self):
        def load_worker():
            success, msg = self.whisper_engine.load_model()
            self.sig_model_status.emit(success, msg)

        self.sig_model_status.connect(self._on_model_loaded)
        threading.Thread(target=load_worker, daemon=True).start()

        self.hotkeys.start()
        self.tray.show()

    def _on_model_loaded(self, success: bool, msg: str):
        if success:
            badge_text = f"⚡ {self.whisper_engine.active_device.upper()} Active"
            if self.whisper_engine.active_device == "cuda":
                badge_text = f"⚡ RTX 4060 — CUDA ({self.whisper_engine.compute_type})"
            self.settings_window.gpu_badge.setText(badge_text)
            self.tray.show_message(
                "Windows STT Ready",
                f"Model '{self.whisper_engine.model_name}' active on {self.whisper_engine.active_device.upper()}"
            )
        else:
            self.settings_window.gpu_badge.setText("❌ Model Failed")
            self.tray.show_message("Windows STT Error", msg)

    def _on_hotkey_start_record(self, mode: str):
        self.sig_start_recording.emit(mode)

    def _on_hotkey_stop_record(self, mode: str):
        self.sig_stop_recording.emit(mode)

    def _handle_start_recording(self, mode: str):
        dev_idx = self.config.get("input_device_index")
        started = self.recorder.start(device_index=dev_idx)
        if started and self.config.get("overlay_enabled", True):
            self.overlay.sig_recording_started.emit(mode)

    def _handle_stop_recording(self, mode: str):
        audio_data = self.recorder.stop()
        if audio_data is None:
            self.overlay.sig_transcription_done.emit("", 0.0)
            return

        if self.config.get("overlay_enabled", True):
            self.overlay.sig_transcribing.emit()

        threading.Thread(
            target=self._transcribe_worker,
            args=(audio_data,),
            daemon=True,
        ).start()

    def _transcribe_worker(self, audio_data: np.ndarray):
        result = self.whisper_engine.transcribe(audio_data)
        text = result.get("text", "")
        latency = result.get("latency", 0.0)

        if text:
            self.injector.inject(text)

        self.sig_transcription_finished.emit(text, latency)

    def _handle_transcription_finished(self, text: str, latency: float):
        if self.config.get("overlay_enabled", True):
            self.overlay.sig_transcription_done.emit(text, latency)

        self.settings_window.add_history_entry(text, latency)

    def _on_settings_updated(self, new_config: Dict[str, Any]):
        self.config = new_config
        self.injector.method = self.config.get("injection_method", "clipboard")
        self.hotkeys.update_hotkeys(
            self.config.get("hotkey_hold", "<ctrl>+<space>"),
            self.config.get("hotkey_toggle", "<ctrl>+<shift>+<space>"),
        )
        print("[Windows STT] Configuration dynamically updated.")

    def _reload_model(self, model_name: str):
        self.config["model_name"] = model_name
        save_config(self.config)
        self.tray.update_model(model_name)
        self.settings_window.gpu_badge.setText("⏳ Loading Model...")
        self.tray.show_message("Loading Model", f"Loading '{model_name}' on GPU...")

        def reload_worker():
            self.whisper_engine.model_name = model_name
            success, msg = self.whisper_engine.load_model()
            self.sig_model_status.emit(success, msg)

        threading.Thread(target=reload_worker, daemon=True).start()

    def _toggle_recording_manual(self):
        if self.recorder.is_recording:
            self._handle_stop_recording("toggle")
        else:
            self._handle_start_recording("toggle")

    def _show_settings(self):
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _exit_app(self):
        print("[Windows STT] Shutting down subsystem...")
        self.hotkeys.stop()
        if self.recorder.is_recording:
            self.recorder.stop()
        cleanup_pid()
        QApplication.quit()


def main():
    # Set Windows Application User Model ID for clean Task Manager identification
    if sys.platform == "win32":
        try:
            app_id = "Antigravity.WindowsSTT.VoiceSubsystem.1.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass

    # Enforce single instance
    mutex = ensure_single_instance()
    if sys.platform == "win32" and mutex is None:
        print("[Windows STT] Another instance of Windows STT is already running!")
        # If launched with a GUI, show a brief informational alert
        app_check = QApplication(sys.argv)
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Windows STT")
        box.setText("Windows STT is already running in the background!\n\nLook for the cyan microphone icon in your Windows System Tray (near the clock).")
        box.exec()
        sys.exit(0)

    register_pid()
    atexit.register(cleanup_pid)

    app = QApplication(sys.argv)
    app.setApplicationName("Windows STT")
    app.setApplicationDisplayName("Windows STT — Voice Typing Subsystem")
    app.setOrganizationName("Antigravity")
    app.setQuitOnLastWindowClosed(False)

    config = load_config()
    coordinator = AppCoordinator(config)

    if "--settings" in sys.argv:
        coordinator._show_settings()

    ret = app.exec()
    cleanup_pid()
    sys.exit(ret)


if __name__ == "__main__":
    main()
