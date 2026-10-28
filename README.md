# Windows STT — Antigravity Voice Typing Subsystem (Faster-Whisper CUDA)

A lightning-fast, system-wide Speech-to-Text background utility designed for Windows, powered by **Faster-Whisper** with full **NVIDIA CUDA GPU acceleration (RTX 4060 8GB)** and a Google-inspired OLED True Black interface.

---

## ⚡ Key Highlights

1. **Dual Activation Modes**:
   - **Push-to-Talk (Hold-to-Talk)**: Hold down `Ctrl + Space` (or `Win + Space` / `Alt + Space`), speak, and release. The text is transcribed and typed directly at your cursor in milliseconds.
   - **Toggle Mode (Hands-Free)**: Press `Ctrl + Shift + Space` (or `Win + Shift + Space`) once. Speak continuously for as long as you want. Press it again to finish and inject the text.
2. **Seamless Background Text Injection**:
   - Works across **any** Windows application (Chrome, VS Code, Slack, Word, Discord, Notepad, etc.).
   - Uses an intelligent clipboard-restore mechanism (preserves whatever you had copied before dictating) with fallback to direct keystrokes.
   - Automatically neutralizes any Windows menu bar focus if using `Alt`.
3. **NVIDIA RTX 4060 GPU Acceleration**:
   - Leverages `faster-whisper` on CTranslate2 with `float16` Tensor Core acceleration.
   - Sub-second latency (~180ms for sentences).
4. **Google-Inspired OLED Black UI**:
   - **Floating Status Pill**: Minimal, floating `#000000` pill with live voice waveform equalizer and status dots. Crucially uses Windows `WS_EX_NOACTIVATE` so it **never steals keyboard focus** from the window you are typing in.
   - **Control Hub & Settings**: Manage Whisper models, customize hotkeys, test your microphone live, and review recent transcription history.
   - **System Tray**: Runs silently in the background with a quick-access context menu.

---

## 🚀 Quick Start

### 1. Launch the Subsystem
- **Double-click `run.bat`**: Starts the subsystem silently in the background (accessible via the System Tray icon near your Windows clock).
- **Double-click `run_debug.bat`**: Starts the subsystem with a console window and opens the Control Hub immediately.

### 2. Default Hotkeys
| Action | Default Hotkey | Behavior |
| :--- | :--- | :--- |
| **Push-to-Talk** | `<ctrl>+<space>` | Hold to speak, release to insert text. |
| **Toggle Mode** | `<ctrl>+<shift>+<space>` | Press once to start, speak freely, press again to insert. |

> **Customizing Hotkeys**: Open the Control Hub (double-click the tray icon or run `run_debug.bat`) to change hotkeys to anything you like, such as `<win>+<space>`, `<caps_lock>`, or `<alt>+<space>`. Dedicated Escape signals automatically cancel Windows menu bar states.

---

## ⚙ Configuration (`config.json`)

You can edit `config.json` directly or use the Settings UI:

```json
{
  "model_name": "small.en",
  "device": "cuda",
  "compute_type": "float16",
  "hotkey_hold": "<alt>+<space>",
  "hotkey_toggle": "<alt>+<shift>+<space>",
  "input_device_index": null,
  "injection_method": "clipboard",
  "restore_clipboard": true,
  "overlay_enabled": true,
  "language": "en",
  "vad_filter": true
}
```

### Supported Whisper Models:
- `tiny.en`: Ultra-fast (~50ms latency, ~150MB VRAM)
- `base.en`: Very fast (~100ms latency, ~250MB VRAM)
- `small.en`: **Recommended default** (~180ms latency, ~500MB VRAM, excellent accuracy)
- `medium.en`: High accuracy (~350ms latency, ~1.5GB VRAM)
- `medium`: Multilingual support
- `large-v3-turbo`: Maximum accuracy for complex vocabulary (~500ms latency, ~2.5GB VRAM)

---

## 🛠 Project Structure

```
t:\Stuffs\STT\
├── app/
│   ├── audio/
│   │   └── recorder.py         # 16kHz mono audio stream & real-time RMS visualizer
│   ├── engine/
│   │   ├── whisper_worker.py   # Faster-Whisper worker with CUDA DLL auto-loader
│   │   └── injector.py         # Native Windows text injection & clipboard restorer
│   ├── hotkeys/
│   │   └── listener.py         # Global keyboard hooks (Push-to-Talk & Toggle)
│   ├── ui/
│   │   ├── styles.py           # Google OLED Dark theme & QSS stylesheets
│   │   ├── overlay.py          # Non-activating floating status pill (WS_EX_NOACTIVATE)
│   │   ├── settings_window.py  # Control Hub with live mic test & transcription history
│   │   └── tray.py             # Windows System Tray icon & context menu
│   ├── config.py               # Settings loader & manager
│   └── main.py                 # Core application coordinator
├── config.json                 # Persistent settings
├── requirements.txt            # Python dependencies
├── run.bat                     # Background launcher
├── run_debug.bat               # Console / debug launcher
└── README.md                   # This documentation
```

