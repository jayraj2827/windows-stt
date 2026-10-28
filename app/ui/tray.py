"""
System Tray integration for STT Subsystem.
Provides unobtrusive background operation with quick access menu.
"""
from typing import Callable, Optional
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


def create_tray_icon() -> QIcon:
    """Dynamically generate a high-DPI OLED black & Google cyan microphone tray icon."""
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Dark background circle
    painter.setBrush(QColor(18, 18, 18))
    painter.setPen(QColor(48, 49, 52))
    painter.drawEllipse(2, 2, size - 4, size - 4)

    # Cyan Mic Body
    painter.setBrush(QColor(138, 180, 248))
    painter.setPen(Qt.PenStyle.NoPen)
    # Capsule
    painter.drawRoundedRect(24, 14, 16, 26, 8, 8)

    # Mic Stand arc
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QColor(138, 180, 248))
    painter.pen().setWidth(3)
    painter.drawArc(18, 24, 28, 22, 0, -180 * 16)
    # Stem & Base
    painter.drawLine(32, 46, 32, 54)
    painter.drawLine(24, 54, 40, 54)

    painter.end()
    return QIcon(pixmap)


class TrayManager(QObject):
    sig_open_settings = pyqtSignal()
    sig_toggle_recording = pyqtSignal()
    sig_switch_model = pyqtSignal(str)
    sig_exit = pyqtSignal()

    def __init__(self, current_model: str = "small.en", parent=None):
        super().__init__(parent)
        self.current_model = current_model
        self.tray = QSystemTrayIcon(parent)
        self.tray.setIcon(create_tray_icon())
        self.tray.setToolTip("Antigravity Voice Typing (Faster-Whisper CUDA)")

        self._build_menu()
        self.tray.activated.connect(self._on_tray_activated)

    def _build_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #0e0e0e;
                color: #e8eaed;
                border: 1px solid #303134;
                border-radius: 8px;
                padding: 6px;
                font-family: 'Segoe UI', sans-serif;
            }
            QMenu::item {
                padding: 6px 20px 6px 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1f2a3d;
                color: #8ab4f8;
            }
            QMenu::separator {
                height: 1px;
                background-color: #262626;
                margin: 4px 0px;
            }
        """)

        # Title Item
        title_action = menu.addAction("🎙 Antigravity Voice Subsystem")
        title_action.setEnabled(False)
        menu.addSeparator()

        # Settings
        settings_action = menu.addAction("Open Control Hub & Settings")
        settings_action.triggered.connect(self.sig_open_settings.emit)

        # Toggle recording
        toggle_action = menu.addAction("Toggle Voice Typing")
        toggle_action.triggered.connect(self.sig_toggle_recording.emit)

        # Model Selector Submenu
        model_menu = menu.addMenu("Whisper Model")
        models = [
            ("tiny.en (Fastest)", "tiny.en"),
            ("base.en (Ultra-fast)", "base.en"),
            ("small.en (Recommended)", "small.en"),
            ("medium.en (High accuracy)", "medium.en"),
            ("medium (Multilingual)", "medium"),
            ("large-v3-turbo (Best accuracy)", "large-v3-turbo"),
        ]

        for label, model_id in models:
            action = model_menu.addAction(label)
            action.setCheckable(True)
            if model_id == self.current_model:
                action.setChecked(True)
            action.triggered.connect(lambda checked, mid=model_id: self.sig_switch_model.emit(mid))

        menu.addSeparator()

        # Exit
        exit_action = menu.addAction("Exit Subsystem")
        exit_action.triggered.connect(self.sig_exit.emit)

        self.tray.setContextMenu(menu)

    def show(self):
        self.tray.show()

    def update_model(self, model_name: str):
        self.current_model = model_name
        self._build_menu()

    def show_message(self, title: str, message: str):
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 2000)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.sig_open_settings.emit()

