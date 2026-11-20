# Friday STT & Web Studio (Faster-Whisper CUDA)

A lightning-fast, system-wide Speech-to-Text background utility and offline Web Studio powered by **Faster-Whisper** with full **NVIDIA CUDA GPU acceleration (RTX 4060 8GB)** and a Google-inspired OLED True Black interface.

---

## ⚡ Two Dedicated Subsystems

### 1. 🖥️ Friday STT — Desktop Real-Time Assistant (`run.bat`)
* **Push-to-Talk (Hold-to-Talk)**: Hold down `Ctrl + Space`, speak, and release to paste directly into any active Windows application.
* **Toggle Mode (Hands-Free)**: Press `Ctrl + Shift + Space` once to speak continuously, press again to paste.
* **Live Progressive Streaming Speech-to-Text**: Words stream **live in real time** right inside the floating OLED pill as you speak!
* **Clipboard Safe Mode**: Every transcript is guaranteed retained on your clipboard, so even if no text box is focused, you never lose your speech.
* **On-Demand Microphone**: Microphone is completely closed and released when idle; the Windows microphone taskbar icon is 100% OFF during idle.
* **True 6-Band FFT Spectral Equalizer**: Ultra-low 32ms audio blocksize with acoustic A-weighted vocal bands synced 1:1 with spoken syllables.

### 2. 🌐 Friday Web Studio — Offline Audio Transcription & Translation (`run_web.bat`)
* **Drag-and-Drop File Upload**: Accepts `.mp3`, `.wav`, `.m4a`, `.mp4`, `.flac`, `.ogg`, `.webm`, `.aac` (up to 500MB).
* **Dual Neural Tasks**:
  * 📝 **Transcribe**: Transcribes speech in its original spoken language with accurate timestamps.
  * 🌐 **Translate to English**: Offline neural translation from 99+ languages directly into English text on your RTX 4060 GPU with 0 cloud calls or API keys!
* **Synchronized Audio Player**: Click on any segment timestamp in the transcript to jump the audio player straight to that moment.
* **One-Click Actions**:
  * 📋 **Copy to Clipboard**: Instant copy with feedback toast.
  * 💾 **Export**: Download as clean plain text (`.txt`), SubRip subtitles (`.srt`), or WebVTT (`.vtt`).
* **Direct Access from Desktop Hub**: Click the **"🌐 Launch Web Studio"** button inside the Control Hub anytime.

---

## 🚀 Quick Start

### Launching Friday STT (Desktop Assistant):
- **To Start**: Double-click **`run.bat`** (runs silently in the background with the cyan microphone icon in your Windows System Tray).
- **To Stop**: Double-click **`stop.bat`** (instantly terminates any running instance).
- **To Debug / Test**: Double-click **`run_debug.bat`** (opens the Control Hub & console).

### Launching Friday Web Studio:
- **To Start**: Double-click **`run_web.bat`** (starts the local server and automatically opens `http://127.0.0.1:8765` in your browser).
- **Or from Desktop Hub**: Double-click the tray icon to open the Control Hub, then click **"🌐 Launch Web Studio"**.

---

## 🛠 Project Structure

```
t:\Stuffs\STT\
├── app/
│   ├── core/                   # 🧠 Shared offline AI & utilities
│   │   ├── whisper_engine.py   # Unified Faster-Whisper worker (CUDA float16, RTX 4060)
│   │   ├── injector.py         # Windows text injection & safe clipboard retention
│   │   └── formatters.py       # Exporters (TXT, SRT, VTT timestamps)
│   ├── web/                    # 🌐 Friday Web Studio (Offline Browser Interface)
│   │   ├── server.py           # Multi-threaded local server (http://127.0.0.1:8765)
│   │   └── static/
│   │       └── index.html      # Responsive OLED Dark single-page studio
│   ├── audio/
│   │   └── recorder.py         # On-demand 16kHz audio capture & FFT visualizer
│   ├── hotkeys/
│   │   └── listener.py         # Global keyboard hooks (Push-to-Talk & Toggle)
│   ├── ui/
│   │   ├── styles.py           # Google OLED Dark theme & QSS stylesheets
│   │   ├── overlay.py          # Non-activating floating status pill (WS_EX_NOACTIVATE)
│   │   ├── settings_window.py  # Control Hub with mic test & Web Studio launcher
│   │   └── tray.py             # System tray icon with quick settings & exit
│   ├── config.py               # Configuration loader & persistent store
│   └── main.py                 # Desktop STT coordinator
├── run.bat                     # Launches Desktop STT Assistant
├── run_web.bat                 # Launches Friday Web Studio
├── run_debug.bat               # Launches STT in debug console mode
└── stop.bat                    # Stops all background instances
```
│   │   └── tray.py             # Windows System Tray icon & context menu
│   ├── config.py               # Settings loader & manager
│   └── main.py                 # Core application coordinator
├── config.json                 # Persistent settings
├── requirements.txt            # Python dependencies
├── run.bat                     # Background launcher
├── run_debug.bat               # Console / debug launcher
└── README.md                   # This documentation
```

