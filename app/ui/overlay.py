"""
Floating Status Pill Overlay for Windows STT Subsystem.
Configured with Windows WS_EX_NOACTIVATE so it NEVER steals focus from active applications.
Features:
- Real-time 6-band FFT spectral visualizer syncing 1:1 with spoken syllables and words.
- Live streaming transcription text preview (words appear progressively as you speak).
- Fixed-size anti-jitter layout (460x52px) with Google OLED dark aesthetics.
- Breathing radial glow status dot.
"""
import ctypes
import math
import sys
from typing import List, Optional
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
            pulse = (math.sin(self._pulse_phase) + 1.0) / 2.0
            glow_radius = 7.0 + pulse * 5.0
            core_radius = 4.5

            gradient = QRadialGradient(cx, cy, glow_radius)
            gradient.setColorAt(0.0, QColor(234, 67, 53, int(170 + pulse * 70)))
            gradient.setColorAt(0.6, QColor(234, 67, 53, int(50 * pulse)))
            gradient.setColorAt(1.0, QColor(234, 67, 53, 0))

            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx - glow_radius), int(cy - glow_radius), int(glow_radius * 2), int(glow_radius * 2))

            painter.setBrush(QColor(234, 67, 53))
            painter.drawEllipse(int(cx - core_radius), int(cy - core_radius), int(core_radius * 2), int(core_radius * 2))

        elif self.state == "transcribing":
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
            painter.setBrush(QColor(52, 168, 83))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(int(cx - 7), int(cy - 7), 14, 14)

            pen = QPen(QColor(255, 255, 255), 1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(int(cx - 3), int(cy), int(cx - 1), int(cy + 3))
            painter.drawLine(int(cx - 1), int(cy + 3), int(cx + 4), int(cy - 3))


class AudioWaveVisualizer(QWidget):
    """
    Real-time 6-band FFT spectral equalizer.
    Bands correspond to real voice acoustic spectrum (vowel pitch, resonance, formants, consonants, sibilance).
    100% reactive to vocal input with zero artificial sine oscillations.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(58, 26)
        self.num_bars = 6
        self.band_levels = [0.0] * self.num_bars
        self.bar_heights = [3.5] * self.num_bars
        self.target_heights = [3.5] * self.num_bars

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate_step)
        self.anim_timer.start(25)  # 40 FPS

    def set_bands(self, bands: List[float]):
        """Receive live 6-band normalized energy from AudioRecorder."""
        if len(bands) >= self.num_bars:
            self.band_levels = [float(b) for b in bands[:self.num_bars]]

    def set_level(self, level: float):
        """Fallback for overall RMS."""
        pass

    def _animate_step(self):
        for i in range(self.num_bars):
            val = self.band_levels[i]
            if val > 0.05:
                # Active vocal frequency response: jumps immediately with speech
                target = max(3.5, min(24.0, 3.5 + val * 20.5))
            else:
                # Still resting baseline when silent (no fake sine oscillation)
                target = 3.5

            self.target_heights[i] = target
            diff = self.target_heights[i] - self.bar_heights[i]
            # Fast attack (0.65) for instant reaction to words, smooth decay (0.32)
            easing = 0.65 if diff > 0 else 0.32
            self.bar_heights[i] += diff * easing

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

            val = self.band_levels[i]
            if val > 0.06 or h > 6.0:
                # Active speaking (Vibrant Google Material soft blue #8ab4f8)
                color = QColor(138, 180, 248)
            else:
                # Silent resting color (deep muted gray)
                color = QColor(70, 74, 80)

            painter.setBrush(QBrush(color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(int(x), int(y), int(bar_width), int(h), 1.5, 1.5)


class FloatingOverlay(QWidget):
    """
    Non-activating floating status pill.
    Features live streaming progressive text display and real-time FFT visualizer.
    """
    sig_recording_started = pyqtSignal(str)
    sig_transcribing = pyqtSignal()
    sig_transcription_done = pyqtSignal(str, float)
    sig_audio_level = pyqtSignal(float)
    sig_audio_bands = pyqtSignal(list)
    sig_streaming_partial = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        # Fixed width and height (460x52) so layout NEVER jumps or shifts!
        self.setFixedSize(460, 52)

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
                background-color: rgba(6, 6, 6, 246);
                border: 1px solid #282828;
                border-radius: 26px;
            }
        """)

        pill_layout = QHBoxLayout(self.container)
        pill_layout.setContentsMargins(16, 0, 16, 0)
        pill_layout.setSpacing(12)

        # Pulsing Glow Dot
        self.dot = PulsingGlowDot(self.container)

        # Text Container (Live streaming text display)
        self.label_container = QWidget(self.container)
        text_layout = QHBoxLayout(self.label_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)

        self.label = QLabel("Listening...", self.label_container)
        self.label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: 500; font-family: 'Segoe UI', 'Google Sans', sans-serif;")

        self.sublabel = QLabel("", self.label_container)
        self.sublabel.setStyleSheet("color: #9aa0a6; font-size: 11px; font-family: 'Segoe UI', sans-serif;")

        text_layout.addWidget(self.label)
        text_layout.addWidget(self.sublabel)
        text_layout.addStretch()

        # Dynamic FFT Equalizer
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
        self.sig_audio_bands.connect(self.wave.set_bands)
        self.sig_streaming_partial.connect(self.on_streaming_partial)

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
        self.sublabel.setStyleSheet("color: #9aa0a6; font-size: 11px;")
        self.wave.setVisible(True)
        self._position_on_screen()
        self.show()

    def on_streaming_partial(self, partial_text: str):
        """Called progressively during live streaming speech-to-text."""
        if not partial_text:
            return
        # Keep the latest spoken words visible if text exceeds available space
        if len(partial_text) > 36:
            preview = "..." + partial_text[-33:]
        else:
            preview = partial_text

        self.label.setText(f'"{preview}"')
        self.sublabel.setText("live")
        self.sublabel.setStyleSheet("color: #8ab4f8; font-size: 11px; font-weight: 600;")

    def on_transcribing(self):
        """Called when final transcription pass is being performed."""
        self.dot.set_state("transcribing")
        self.sublabel.setText("finalizing")
        self.sublabel.setStyleSheet("color: #fbbc04; font-size: 11px;")
        self.wave.setVisible(False)
        self.update()

    def on_transcription_done(self, text: str, latency: float):
        """Called when transcription is injected."""
        self.dot.set_state("done")
        if text:
            preview = ("..." + text[-30:]) if len(text) > 33 else text
            self.label.setText(f'"{preview}"')
            self.sublabel.setText(f"{latency}s")
            self.sublabel.setStyleSheet("color: #81c995; font-size: 11px;")
        else:
            self.label.setText("No speech detected")
            self.sublabel.setText("")
        self.wave.setVisible(False)
        self.update()
        # Auto hide after 1.4s
        self.hide_timer.start(1400)
