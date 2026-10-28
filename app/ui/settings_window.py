"""
Settings and Control Hub for STT Subsystem.
Google OLED Dark UI aesthetic with comprehensive system controls.
"""
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
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
    QRadioButton,
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

    def __init__(self, config: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.config = config
        self.test_recorder: Optional[AudioRecorder] = None
        self.is_testing_mic = False

        self.setWindowTitle("Antigravity STT Subsystem — Control Hub")
        self.setMinimumSize(640, 720)
        self.resize(680, 780)
        self.setStyleSheet(OLED_BLACK_QSS)

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
        self.status_feedback.setStyleSheet("color: #8ab4f8; font-size: 12px;")

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
            "tiny.en (Fastest, ~150MB VRAM)",
            "base.en (Ultra-fast, ~250MB VRAM)",
            "small.en (Recommended, ~500MB VRAM)",
            "medium.en (High accuracy, ~1.5GB VRAM)",
            "medium (Multilingual, ~1.5GB VRAM)",
            "large-v3-turbo (Best accuracy, ~2.5GB VRAM)",
        ])
        row.addWidget(lbl)
        row.addWidget(self.combo_model, 1)
        layout.addLayout(row)

        desc = QLabel(
            "Note: Running on your RTX 4060 GPU with float16 Tensor Cores. "
            "Switching models will load the new weights instantly into memory.",
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

        # Push to talk
        row1 = QHBoxLayout()
        lbl1 = QLabel("Push-to-Talk (Hold):", card)
        lbl1.setFixedWidth(160)
        self.edit_hold = QLineEdit(card)
        self.edit_hold.setPlaceholderText("<ctrl>+<space>")
        row1.addWidget(lbl1)
        row1.addWidget(self.edit_hold)
        layout.addLayout(row1)

        # Toggle mode
        row2 = QHBoxLayout()
        lbl2 = QLabel("Toggle Mode (Hands-Free):", card)
        lbl2.setFixedWidth(160)
        self.edit_toggle = QLineEdit(card)
        self.edit_toggle.setPlaceholderText("<ctrl>+<shift>+<space>")
        row2.addWidget(lbl2)
        row2.addWidget(self.edit_toggle)
        layout.addLayout(row2)

        hint = QLabel(
            "Push-to-Talk records while the keys are held. Toggle Mode starts on press and stops on next press.\n"
            "Supported modifiers: <alt>, <ctrl>, <shift>, <win>, <space>, <caps_lock>, or letters (e.g. <alt>+z).",
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
        self.combo_device.addItem("Windows Default Audio Input", None)
        # Populate detected devices
        devices = AudioRecorder.get_input_devices()
        for dev_idx, dev_name, is_def in devices:
            text = f"{dev_name} {'(System Default)' if is_def else ''}"
            self.combo_device.addItem(text, dev_idx)

        row.addWidget(lbl)
        row.addWidget(self.combo_device, 1)
        layout.addLayout(row)

        # Live Audio Level Meter
        meter_layout = QHBoxLayout()
        self.test_btn = QPushButton("Test Microphone", card)
        self.test_btn.setFixedWidth(140)
        self.test_btn.clicked.connect(self._toggle_mic_test)

        self.audio_meter = QProgressBar(card)
        self.audio_meter.setRange(0, 100)
        self.audio_meter.setValue(0)
        self.audio_meter.setTextVisible(False)

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

        self.btn_group_injection = QButtonGroup(card)
        self.radio_clipboard = QRadioButton("Clipboard Paste (Fastest, preserves existing clipboard)", card)
        self.radio_typing = QRadioButton("Simulated Typing (Character by character)", card)
        self.btn_group_injection.addButton(self.radio_clipboard)
        self.btn_group_injection.addButton(self.radio_typing)

        layout.addWidget(self.radio_clipboard)
        layout.addWidget(self.radio_typing)

        self.check_overlay = QCheckBox("Show floating status pill widget while speaking", card)
        layout.addWidget(self.check_overlay)

        return card

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
        self.edit_hold.setText(self.config.get("hotkey_hold", "<alt>+<space>"))
        self.edit_toggle.setText(self.config.get("hotkey_toggle", "<alt>+<shift>+<space>"))

        # Input device
        selected_dev = self.config.get("input_device_index")
        for i in range(self.combo_device.count()):
            if self.combo_device.itemData(i) == selected_dev:
                self.combo_device.setCurrentIndex(i)
                break

        # Injection
        method = self.config.get("injection_method", "clipboard")
        if method == "typing":
            self.radio_typing.setChecked(True)
        else:
            self.radio_clipboard.setChecked(True)

        self.check_overlay.setChecked(self.config.get("overlay_enabled", True))

    def _toggle_mic_test(self):
        """Toggle live microphone volume testing."""
        if self.is_testing_mic:
            # Stop test
            if self.test_recorder:
                self.test_recorder.stop()
                self.test_recorder = None
            self.audio_meter.setValue(0)
            self.test_btn.setText("Test Microphone")
            self.is_testing_mic = False
        else:
            # Start test
            dev_idx = self.combo_device.currentData()
            self.test_recorder = AudioRecorder()
            self.test_recorder.set_level_callback(self._on_mic_level)
            if self.test_recorder.start(device_index=dev_idx):
                self.is_testing_mic = True
                self.test_btn.setText("Stop Testing")
            else:
                self.status_feedback.setText("Could not start test microphone.")

    def _on_mic_level(self, level: float):
        val = int(level * 100)
        QTimer.singleShot(0, lambda: self.audio_meter.setValue(val))

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
        # Stop mic test if running
        if self.is_testing_mic:
            self._toggle_mic_test()

        # Extract selected model
        raw_model = self.combo_model.currentText().split(" ")[0]
        model_changed = (raw_model != self.config.get("model_name"))

        self.config["model_name"] = raw_model
        self.config["hotkey_hold"] = self.edit_hold.text().strip() or "<alt>+<space>"
        self.config["hotkey_toggle"] = self.edit_toggle.text().strip() or "<alt>+<shift>+<space>"
        self.config["input_device_index"] = self.combo_device.currentData()
        self.config["injection_method"] = "typing" if self.radio_typing.isChecked() else "clipboard"
        self.config["overlay_enabled"] = self.check_overlay.isChecked()

        save_config(self.config)
        self.sig_settings_changed.emit(self.config)

        if model_changed:
            self.sig_reload_model_requested.emit(raw_model)

        self.status_feedback.setText("✓ Settings saved and applied successfully!")
        QTimer.singleShot(2500, lambda: self.status_feedback.setText(""))

    def closeEvent(self, event):
        # Stop mic test if user closes window
        if self.is_testing_mic:
            self._toggle_mic_test()
        super().closeEvent(event)

