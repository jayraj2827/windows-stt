"""
Google-inspired OLED True Black Theme and QSS stylesheets.
Clean, modern, high-contrast, rounded corners with subtle Material accents.
"""

OLED_BLACK_QSS = """
/* Global Window & Typography */
QWidget {
    background-color: #000000;
    color: #e8eaed;
    font-family: 'Segoe UI', 'Google Sans', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
    selection-background-color: #8ab4f8;
    selection-color: #000000;
}


/* Main Dashboard Card Surfaces */
QFrame#card {
    background-color: #0e0e0e;
    border: 1px solid #202124;
    border-radius: 12px;
}

QFrame#card_subtle {
    background-color: #080808;
    border: 1px solid #1a1a1a;
    border-radius: 8px;
}

/* Headers & Labels */
QLabel#title_label {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 0.5px;
}

QLabel#subtitle_label {
    font-size: 12px;
    color: #9aa0a6;
}

QLabel#section_header {
    font-size: 14px;
    font-weight: 600;
    color: #8ab4f8;
    margin-top: 6px;
    margin-bottom: 2px;
}

QLabel#badge_gpu {
    background-color: #132d1f;
    color: #81c995;
    border: 1px solid #1e4620;
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: 600;
}

/* Buttons */
QPushButton {
    background-color: #1a1a1a;
    color: #e8eaed;
    border: 1px solid #303134;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #252627;
    border: 1px solid #5f6368;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #303134;
}

QPushButton#primary_button {
    background-color: #8ab4f8;
    color: #000000;
    border: none;
    font-weight: 600;
}

QPushButton#primary_button:hover {
    background-color: #aecbfa;
}

QPushButton#primary_button:pressed {
    background-color: #669df6;
}

/* Inputs & Comboboxes */
QComboBox, QLineEdit {
    background-color: #0c0c0c;
    color: #f1f3f4;
    border: 1px solid #2c2c2e;
    border-radius: 8px;
    padding: 7px 12px;
    min-height: 20px;
}

QComboBox:hover, QLineEdit:hover {
    border: 1px solid #5f6368;
}

QComboBox:focus, QLineEdit:focus {
    border: 1px solid #8ab4f8;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #121212;
    border: 1px solid #303134;
    border-radius: 8px;
    color: #e8eaed;
    selection-background-color: #1f2a3d;
    selection-color: #8ab4f8;
    padding: 4px;
}

/* Radio buttons & Checkboxes */
QRadioButton, QCheckBox {
    color: #e8eaed;
    spacing: 8px;
}

QRadioButton::indicator, QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 2px solid #5f6368;
    background-color: #0c0c0c;
}

QRadioButton::indicator:checked, QCheckBox::indicator:checked {
    border: 2px solid #8ab4f8;
    background-color: #8ab4f8;
}

/* Progress / Meter */
QProgressBar {
    background-color: #141414;
    border: 1px solid #282828;
    border-radius: 6px;
    text-align: center;
    color: #ffffff;
    font-size: 10px;
    min-height: 14px;
    max-height: 14px;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8ab4f8, stop:1 #34a853);
    border-radius: 5px;
}

QProgressBar#mic_meter {
    background-color: #0c0c0c;
    border: 1px solid #333333;
    border-radius: 6px;
    text-align: center;
    color: #ffffff;
    font-size: 11px;
    font-weight: 600;
    min-height: 22px;
    max-height: 22px;
}

QProgressBar#mic_meter::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8ab4f8, stop:0.6 #81c995, stop:1.0 #34a853);
    border-radius: 5px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #000000;
    width: 6px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #303134;
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #5f6368;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

OVERLAY_PILL_QSS = """
QFrame#pill_container {
    background-color: rgba(0, 0, 0, 235);
    border: 1px solid #333333;
    border-radius: 20px;
}

QLabel#pill_label {
    color: #ffffff;
    font-size: 13px;
    font-weight: 600;
    font-family: 'Segoe UI', 'Google Sans', sans-serif;
}

QLabel#pill_sublabel {
    color: #9aa0a6;
    font-size: 11px;
    font-family: 'Segoe UI', sans-serif;
}
"""
