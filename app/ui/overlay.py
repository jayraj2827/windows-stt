"""
Floating Status Pill Overlay for STT Subsystem.
Configured with Windows WS_EX_NOACTIVATE so it NEVER steals focus from active applications.
Features fixed-size anti-jitter layout, pulsing glow indicator, and smooth auto-gain audio visualizer.
"""
import ctypes
import math
import sys
from typing import Optional
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)

# Windows Extended Window Styles
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080


class PulsingGlowDot(QWidget):
    """Smooth animated status indicator with breathing radial glow."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.state = "listening"  # "listening", "transcribing", "done"
        self._pulse_phase = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._step)
        self.timer.start(25)

    def set_state(self, state: str):
        self.state = state
        self.update()

    def _step(self):
        self._pulse_phase = (self._pulse_phase + 0.12) % (2 * math.pi)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() / 2, self.height() / 2

        if self.state == "listening":
            # Breathing pulse
            pulse = (math.sin(self._pulse_phase) + 1.0) / 2.0  # 0.0 to 1.0
            glow_radius = 7.0 + pulse * 5.0
            core_radius = 4.5

            # Outer radial glow (Google Coral Red)
            gradient = QRadialGradient(cx, cy, glow_radius)
            gradient.setColorAt(0.0, QColor(234, 67, 53, int(160 + pulse * 70)))
            gradient.setColorAt(0.6, QColor(234, 67, 53, int(50 * pulse)))
            gradient.setColorAt(1.0, QColor(234, 67, 53, 0))

            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx - glow_radius), int(cy - glow_radius), int(glow_radius * 2), int(glow_radius * 2))

            # Solid inner core
            painter.setBrush(QColor(234, 67, 53))
            painter.drawEllipse(int(cx - core_radius), int(cy - core_radius), int(core_radius * 2), int(core_radius * 2))

        elif self.state == "transcribing":
            # Rotating/pulsing amber dot
            pulse = (math.sin(self._pulse_phase * 2) + 1.0) / 2.0
            core_radius = 4.5 + pulse * 1.5

            gradient = QRadialGradient(cx, cy, 9.0)
            gradient.setColorAt(0.0, QColor(251, 188, 4, 200))
            gradient.setColorAt(0.8, QColor(251, 188, 4, int(40 * pulse)))
            gradient.setColorAt(1.0, QColor(251, 188, 4, 0))

            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx - 9), int(cy - 9), 18, 18)

            painter.setBrush(QColor(251, 188, 4))
            painter.drawEllipse(int(cx - core_radius), int(cy - core_radius), int(core_radius * 2), int(core_radius * 2))

        elif self.state == "done":
            # Crisp green checkmark circle
            painter.setBrush(QColor(52, 168, 83))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx - 7), int(cy - 7), 14, 14)

            # Draw white checkmark
            pen = QPen(QColor(255, 255, 255), 1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(int(cx - 3), int(cy), int(cx - 1), int(cy + 3))
            painter.drawLine(int(cx - 1), int(cy + 3), int(cx + 4), int(cy - 3))


class AudioWaveVisualizer(QWidget):
    """
    Fluid 6-bar audio equalizer with auto-gain normalization and idle ambient wave.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(54, 24)
        self.num_bars = 6
        self.current_level = 0.0
        self.bar_heights = [4.0] * self.num_bars
        self.target_heights = [4.0] * self.num_bars
        self._idle_phase = 0.0

        # Bar frequency sensitivities (Google Pixel equalizer profile)
        self.multipliers = [0.65, 0.95, 1.25, 1.15, 0.85, 0.55]

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate_step)
        self.anim_timer.start(25)  # 40 FPS smooth animation

    def set_level(self, level: float):
        """Update live audio level (0.0 to 1.0)."""
        self.current_level = max(0.0, min(1.0, level))

    def _animate_step(self):
        self._idle_phase = (self._idle_phase + 0.14) % (2 * math.pi)

        # Calculate target heights
        for i in range(self.num_bars):
            if self.current_level > 0.03:
                # Active voice wave with responsive height
                base_h = self.current_level * 18.0 * self.multipliers[i]
                target = max(4.0, min(22.0, 4.0 + base_h))
            else:
                # Gentle ambient breathing wave while listening
                ambient = math.sin(self._idle_phase + i * 0.7) * 2.0
                target = max(3.0, 4.5 + ambient)

            self.target_heights[i] = target

            # Elastic easing toward target
            diff = self.target_heights[i] - self.bar_heights[i]
            self.bar_heights[i] += diff * 0.38

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bar_width = 3.5
        gap = 4.5
        start_x = 3.0
        center_y = self.height() / 2.0

        for i, h in enumerate(self.bar_heights):
            x = start_x + i * (bar_width + gap)
            y = center_y - (h / 2.0)

            # Google Material soft blue / cyan gradient
            if self.current_level > 0.05:
                # Active speaking color (vibrant Google blue #8ab4f8)
                color = QColor(138, 180, 248)
            else:
                # Subtle ambient listening gray
                color = QColor(110, 115, 122)

            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(int(x), int(y), int(bar_width), int(h), 1.5, 1.5)


class FloatingOverlay(QWidget):
    """
    Non-activating floating status pill.
    Uses a fixed width & height to completely eliminate jumping, jitter, or layout shift.
    """
    sig_recording_started = pyqtSignal(str)
    sig_transcribing = pyqtSignal()
    sig_transcription_done = pyqtSignal(str, float)
    sig_audio_level = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        # Fixed pill dimensions — absolutely no window resizing on state changes!
        self.setFixedSize(310, 50)

        self._init_ui()
        self._connect_signals()

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.container = QFrame(self)
        self.container.setObjectName("pill_container")
        self.container.setStyleSheet("""
            QFrame#pill_container {
                background-color: rgba(6, 6, 6, 245);
                border: 1px solid #282828;
                border-radius: 24px;
            }
        """)

        pill_layout = QHBoxLayout(self.container)
        pill_layout.setContentsMargins(14, 0, 14, 0)
        pill_layout.setSpacing(10)

        # Pulsing Glow Dot
        self.dot = PulsingGlowDot(self.container)

        # Center Status Text (fixed width to prevent layout shifts)
        self.label_container = QWidget(self.container)
        text_layout = QHBoxLayout(self.label_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)

        self.label = QLabel("Listening...", self.label_container)
        self.label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 600; font-family: 'Segoe UI', 'Google Sans', sans-serif;")

        self.sublabel = QLabel("", self.label_container)
        self.sublabel.setStyleSheet("color: #9aa0a6; font-size: 11px; font-family: 'Segoe UI', sans-serif;")

        text_layout.addWidget(self.label)
        text_layout.addWidget(self.sublabel)
        text_layout.addStretch()

        # Dynamic Audio Wave Equalizer
        self.wave = AudioWaveVisualizer(self.container)

        pill_layout.addWidget(self.dot)
        pill_layout.addWidget(self.label_container, 1)
        pill_layout.addWidget(self.wave)

        layout.addWidget(self.container)

    def _connect_signals(self):
        self.sig_recording_started.connect(self.on_recording_started)
        self.sig_transcribing.connect(self.on_transcribing)
        self.sig_transcription_done.connect(self.on_transcription_done)
        self.sig_audio_level.connect(self.wave.set_level)

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_no_activate_flag()
        self._position_on_screen()

    def _apply_no_activate_flag(self):
        """Set Windows WS_EX_NOACTIVATE style so window never takes focus."""
        if sys.platform == "win32":
            try:
                hwnd = int(self.winId())
                user32 = ctypes.windll.user32
                current_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                new_style = current_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            except Exception as e:
                print(f"[FloatingOverlay] Win32 style config error: {e}")

    def _position_on_screen(self):
        """Position pill centered horizontally near bottom of primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.availableGeometry()
            x = (screen_geo.width() - self.width()) // 2 + screen_geo.x()
            y = screen_geo.height() - self.height() - 48 + screen_geo.y()
            self.move(x, y)

    def on_recording_started(self, mode: str):
        """Called when recording begins."""
        self.hide_timer.stop()
        self.dot.set_state("listening")
        self.label.setText("Listening...")
        self.sublabel.setText(f"({mode.capitalize()})")
        self.wave.setVisible(True)
        self._position_on_screen()
        self.show()

    def on_transcribing(self):
        """Called when audio is being transcribed."""
        self.dot.set_state("transcribing")
        self.label.setText("Transcribing...")
        self.sublabel.setText("RTX 4060")
        self.wave.setVisible(False)
        self.update()

    def on_transcription_done(self, text: str, latency: float):
        """Called when transcription is injected."""
        self.dot.set_state("done")
        if text:
            preview = (text[:22] + "...") if len(text) > 25 else text
            self.label.setText(f'"{preview}"')
            self.sublabel.setText(f"{latency}s")
        else:
            self.label.setText("No speech detected")
            self.sublabel.setText("")
        self.wave.setVisible(False)
        self.update()
        # Auto hide after 1.2s
        self.hide_timer.start(1200)
