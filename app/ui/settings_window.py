"""
Settings and Control Hub for Windows STT Subsystem.
Google OLED Dark UI aesthetic with comprehensive system controls.
"""
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.audio.recorder import AudioRecorder
from app.config import save_config
from app.ui.styles import OLED_BLACK_QSS


class SettingsWindow(QWidget):
    sig_settings_changed = pyqtSignal(dict)
    sig_reload_model_requested = pyqtSignal(str)
    sig_mic_test_level = pyqtSignal(float)

    def __init__(self, config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.config = config
        self.test_recorder: Optional[AudioRecorder] = None
        self.is_testing_mic = False

        self.setWindowTitle("Windows STT — Control Hub")
        self.setMinimumSize(660, 720)
        self.resize(700, 780)
        self.setStyleSheet(OLED_BLACK_QSS)

        self.sig_mic_test_level.connect(self._update_test_meter)

        self._init_ui()
        self._populate_fields()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(18)

        # Header Section
        header_layout = QHBoxLayout()
        header_text_layout = QVBoxLayout()

        title = QLabel("Voice Typing Subsystem", self)
        title.setObjectName("title_label")
        subtitle = QLabel("Background Faster-Whisper subsystem powered by NVIDIA CUDA", self)
        subtitle.setObjectName("subtitle_label")

        header_text_layout.addWidget(title)
        header_text_layout.addWidget(subtitle)
        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()

        # GPU Badge
        self.gpu_badge = QLabel("⚡ RTX 4060 — CUDA Active", self)
        self.gpu_badge.setObjectName("badge_gpu")
        header_layout.addWidget(self.gpu_badge)
        main_layout.addLayout(header_layout)

        # Scroll Area for Cards
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_widget = QWidget()
        cards_layout = QVBoxLayout(scroll_widget)
        cards_layout.setContentsMargins(0, 4, 8, 4)
        cards_layout.setSpacing(16)

        # 1. Model Configuration Card
        cards_layout.addWidget(self._create_model_card())

        # 2. Hotkeys Configuration Card
        cards_layout.addWidget(self._create_hotkeys_card())

        # 3. Audio & Microphone Card
        cards_layout.addWidget(self._create_audio_card())

        # 4. Text Injection Card
        cards_layout.addWidget(self._create_injection_card())

        # 5. Transcription History Card
        cards_layout.addWidget(self._create_history_card())

        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)

        # Bottom Action Bar
        bottom_bar = QHBoxLayout()
        self.status_feedback = QLabel("", self)
        self.status_feedback.setStyleSheet("color: #8ab4f8; font-size: 12px; font-weight: 500;")

        save_btn = QPushButton("Save & Apply Settings", self)
        save_btn.setObjectName("primary_button")
        save_btn.setMinimumHeight(38)
        save_btn.clicked.connect(self._save_and_apply)

        bottom_bar.addWidget(self.status_feedback)
        bottom_bar.addStretch()
        bottom_bar.addWidget(save_btn)
        main_layout.addLayout(bottom_bar)

    def _create_model_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QLabel("Faster-Whisper Model", card)
        header.setObjectName("section_header")
        layout.addWidget(header)

        row = QHBoxLayout()
        lbl = QLabel("Model Variant:", card)
        self.combo_model = QComboBox(card)
        self.combo_model.addItems([
            "small.en (Recommended, ~500MB VRAM)",
            "base.en (Ultra-fast, ~250MB VRAM)",
            "tiny.en (Fastest, ~150MB VRAM)",
            "medium.en (High accuracy, ~1.5GB VRAM)",
            "medium (Multilingual, ~1.5GB VRAM)",
            "large-v3-turbo (Best accuracy, ~2.5GB VRAM)",
        ])
        row.addWidget(lbl)
        row.addWidget(self.combo_model, 1)
        layout.addLayout(row)

        desc = QLabel(
            "Powered by your RTX 4060 GPU with float16 Tensor Cores. "
            "Switching models will load the weights into memory instantly.",
            card
        )
        desc.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        layout.addWidget(desc)

        return card

    def _create_hotkeys_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QLabel("Activation Hotkeys", card)
        header.setObjectName("section_header")
        layout.addWidget(header)

        row1 = QHBoxLayout()
        lbl1 = QLabel("Push-to-Talk (Hold):", card)
        lbl1.setFixedWidth(160)
        self.edit_hold = QLineEdit(card)
        self.edit_hold.setPlaceholderText("<ctrl>+<space>")
        row1.addWidget(lbl1)
        row1.addWidget(self.edit_hold)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        lbl2 = QLabel("Toggle Mode (Hands-Free):", card)
        lbl2.setFixedWidth(160)
        self.edit_toggle = QLineEdit(card)
        self.edit_toggle.setPlaceholderText("<ctrl>+<shift>+<space>")
        row2.addWidget(lbl2)
        row2.addWidget(self.edit_toggle)
        layout.addLayout(row2)

        hint = QLabel(
            "Push-to-Talk records while held down. Toggle Mode starts on press and stops on next press.\n"
            "Supported modifiers: <ctrl>, <shift>, <win>, <alt>, <space>, <caps_lock>, or letters (e.g. <ctrl>+z).",
            card
        )
        hint.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        layout.addWidget(hint)

        return card

    def _create_audio_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QLabel("Microphone & Audio Input", card)
        header.setObjectName("section_header")
        layout.addWidget(header)

        row = QHBoxLayout()
        lbl = QLabel("Input Device:", card)
        self.combo_device = QComboBox(card)

        # Filtered, curated genuine microphones (prioritizing WASAPI)
        devices = AudioRecorder.get_input_devices()
        for dev_idx, label, is_wasapi in devices:
            self.combo_device.addItem(label, dev_idx)

        # Fallback to system default if list empty
        if self.combo_device.count() == 0:
            self.combo_device.addItem("Windows System Default Audio Input", None)

        row.addWidget(lbl)
        row.addWidget(self.combo_device, 1)
        layout.addLayout(row)

        desc = QLabel(
            "Note: Filtered to show only genuine microphone inputs (excluding loopback speakers & stereo mix). "
            "WASAPI provides bit-exact recording with zero resampling noise for maximum Whisper accuracy.",
            card
        )
        desc.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        layout.addWidget(desc)

        # Live Audio Level Meter
        meter_layout = QHBoxLayout()
        self.test_btn = QPushButton("Test Microphone", card)
        self.test_btn.setFixedWidth(140)
        self.test_btn.clicked.connect(self._toggle_mic_test)

        self.audio_meter = QProgressBar(card)
        self.audio_meter.setObjectName("mic_meter")
        self.audio_meter.setRange(0, 100)
        self.audio_meter.setValue(0)
        self.audio_meter.setTextVisible(True)
        self.audio_meter.setFormat("Mic Level: 0%")

        meter_layout.addWidget(self.test_btn)
        meter_layout.addWidget(self.audio_meter)
        layout.addLayout(meter_layout)

        return card

    def _create_injection_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QLabel("Text Output & Injection", card)
        header.setObjectName("section_header")
        layout.addWidget(header)

        # Checkboxes for text injection mode
        self.check_clipboard = QCheckBox("Clipboard Paste (Recommended — Instant & preserves existing clipboard)", card)
        self.check_typing = QCheckBox("Simulated Typing (Character by character fallback)", card)
        self.check_overlay = QCheckBox("Show floating status pill widget while speaking", card)

        self.check_clipboard.toggled.connect(self._on_clipboard_toggled)
        self.check_typing.toggled.connect(self._on_typing_toggled)

        layout.addWidget(self.check_clipboard)
        layout.addWidget(self.check_typing)
        layout.addWidget(self.check_overlay)

        return card

    def _on_clipboard_toggled(self, checked: bool):
        if checked:
            self.check_typing.blockSignals(True)
            self.check_typing.setChecked(False)
            self.check_typing.blockSignals(False)
        elif not self.check_typing.isChecked():
            self.check_clipboard.blockSignals(True)
            self.check_clipboard.setChecked(True)
            self.check_clipboard.blockSignals(False)

    def _on_typing_toggled(self, checked: bool):
        if checked:
            self.check_clipboard.blockSignals(True)
            self.check_clipboard.setChecked(False)
            self.check_clipboard.blockSignals(False)
        elif not self.check_clipboard.isChecked():
            self.check_typing.blockSignals(True)
            self.check_typing.setChecked(True)
            self.check_typing.blockSignals(False)

    def _create_history_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QLabel("Recent Transcriptions", card)
        header.setObjectName("section_header")
        layout.addWidget(header)

        self.history_list = QListWidget(card)
        self.history_list.setMaximumHeight(130)
        self.history_list.setStyleSheet(
            "background-color: #0c0c0c; border: 1px solid #202124; border-radius: 8px; padding: 4px;"
        )
        layout.addWidget(self.history_list)

        return card

    def _populate_fields(self):
        # Model
        target_model = self.config.get("model_name", "small.en")
        for i in range(self.combo_model.count()):
            if self.combo_model.itemText(i).startswith(target_model):
                self.combo_model.setCurrentIndex(i)
                break

        # Hotkeys
        self.edit_hold.setText(self.config.get("hotkey_hold", "<ctrl>+<space>"))
        self.edit_toggle.setText(self.config.get("hotkey_toggle", "<ctrl>+<shift>+<space>"))

        # Input device
        selected_dev = self.config.get("input_device_index")
        matched = False
        if selected_dev is not None:
            for i in range(self.combo_device.count()):
                if self.combo_device.itemData(i) == selected_dev:
                    self.combo_device.setCurrentIndex(i)
                    matched = True
                    break
        # If no custom device set, default to index 0 (which is the recommended WASAPI device)
        if not matched and self.combo_device.count() > 0:
            self.combo_device.setCurrentIndex(0)

        # Injection checkboxes
        method = self.config.get("injection_method", "clipboard")
        if method == "typing":
            self.check_typing.setChecked(True)
            self.check_clipboard.setChecked(False)
        else:
            self.check_clipboard.setChecked(True)
            self.check_typing.setChecked(False)

        self.check_overlay.setChecked(self.config.get("overlay_enabled", True))

    def _toggle_mic_test(self):
        """Toggle live microphone volume testing."""
        if self.is_testing_mic:
            if self.test_recorder:
                self.test_recorder.stop()
                self.test_recorder = None
            self.audio_meter.setValue(0)
            self.audio_meter.setFormat("Mic Level: 0%")
            self.test_btn.setText("Test Microphone")
            self.is_testing_mic = False
        else:
            dev_idx = self.combo_device.currentData()
            self.test_recorder = AudioRecorder()
            self.test_recorder.set_level_callback(self._on_mic_level)
            if self.test_recorder.start(device_index=dev_idx):
                self.is_testing_mic = True
                self.test_btn.setText("Stop Testing")
            else:
                self.status_feedback.setText("Could not start test microphone.")

    def _on_mic_level(self, level: float):
        """Callback from PortAudio thread — safely emit Qt signal."""
        self.sig_mic_test_level.emit(level)

    def _update_test_meter(self, level: float):
        """Executed on Qt GUI Main Thread to update visual meter."""
        val = max(0, min(100, int(level * 100)))
        self.audio_meter.setValue(val)
        self.audio_meter.setFormat(f"Live Input Level: {val}%")

    def add_history_entry(self, text: str, latency: float):
        """Add completed transcription to the history list."""
        if not text:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        item_text = f"[{timestamp}] ({latency}s) {text}"
        item = QListWidgetItem(item_text)
        self.history_list.insertItem(0, item)
        if self.history_list.count() > 30:
            self.history_list.takeItem(self.history_list.count() - 1)

    def _save_and_apply(self):
        if self.is_testing_mic:
            self._toggle_mic_test()

        raw_model = self.combo_model.currentText().split(" ")[0]
        model_changed = (raw_model != self.config.get("model_name"))

        self.config["model_name"] = raw_model
        self.config["hotkey_hold"] = self.edit_hold.text().strip() or "<ctrl>+<space>"
        self.config["hotkey_toggle"] = self.edit_toggle.text().strip() or "<ctrl>+<shift>+<space>"
        self.config["input_device_index"] = self.combo_device.currentData()
        self.config["injection_method"] = "typing" if self.check_typing.isChecked() else "clipboard"
        self.config["overlay_enabled"] = self.check_overlay.isChecked()

        save_config(self.config)
        self.sig_settings_changed.emit(self.config)

        if model_changed:
            self.sig_reload_model_requested.emit(raw_model)

        self.status_feedback.setText("✓ Settings saved and applied successfully!")
        QTimer.singleShot(2500, lambda: self.status_feedback.setText(""))

    def closeEvent(self, event):
        if self.is_testing_mic:
            self._toggle_mic_test()
        super().closeEvent(event)
