# Friday STT — Voice Typing System (Faster-Whisper CUDA)

A lightning-fast, system-wide Speech-to-Text background utility powered by **Faster-Whisper** with full **NVIDIA CUDA GPU acceleration (RTX 4060 8GB)** and a Google-inspired OLED True Black interface.

---

## ⚡ Key Highlights

1. **Live Progressive Streaming Speech-to-Text**:
   - Words stream **live in real time** right inside the floating OLED pill as you speak!
   - Powered by low-latency progressive snapshots on your RTX 4060 GPU (~30ms streaming inference).
   - Zero-delay text injection into your active document upon key release.
2. **True 6-Band FFT Spectral Equalizer (Syllable Sync)**:
   - Ultra-low 32ms audio blocksize with real-time Fast Fourier Transform (FFT).
   - Breaks down live audio into 6 distinct vocal acoustic bands (Vocal pitch, Vowels, Formants, Articulation, Sibilance, and Treble air).
   - Waves dance in exact 1:1 synchronization with every spoken word and syllable.
3. **Dual Activation Modes**:
   - **Push-to-Talk (Hold-to-Talk)**: Hold down `Ctrl + Space` (or `Win + Space` / `Alt + Space`), speak, and release to paste.
   - **Toggle Mode (Hands-Free)**: Press `Ctrl + Shift + Space` (or `Win + Shift + Space`) once to speak continuously, press again to paste.
4. **Seamless Background Text Injection**:
   - Works across **any** Windows application (Chrome, VS Code, Slack, Word, Discord, Notepad, etc.).
   - Uses an intelligent clipboard-restore mechanism (preserves whatever you had copied before dictating) with fallback to direct keystrokes.
   - Automatically neutralizes any Windows menu bar focus if using `Alt`.
5. **NVIDIA RTX 4060 GPU Acceleration**:
   - Leverages `faster-whisper` on CTranslate2 with `float16` Tensor Core acceleration.
   - Sub-second latency (~66ms for inference).
6. **Google-Inspired OLED Black UI**:
   - **Floating Status Pill**: Minimal, floating `#000000` pill with live voice waveform equalizer and status dots. Crucially uses Windows `WS_EX_NOACTIVATE` so it **never steals keyboard focus** from the window you are typing in.
   - **Control Hub & Settings**: Manage Whisper models, customize hotkeys, test your microphone live, and review recent transcription history.
   - **System Tray**: Runs silently in the background with a quick-access context menu.

---

## 🚀 Quick Start

### 1. Launch & Stop
- **To Start**: Double-click **`run.bat`** (runs silently in the background with the cyan microphone icon in your Windows System Tray).
- **To Stop**: Double-click **`stop.bat`** (instantly terminates any running instance).
- **To Debug / Test**: Double-click **`run_debug.bat`** (opens the Control Hub & console).
- **From Tray**: Right-click the cyan microphone icon in your Windows Taskbar tray (click `^` overflow if hidden) -> click **Exit Subsystem**.

> **Single-Instance Protection**: A Windows named mutex prevents duplicate instances from running. Launching `run.bat` when an instance is already active simply alerts you without creating conflicts.

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
  "hotkey_hold": "<ctrl>+<space>",
  "hotkey_toggle": "<ctrl>+<shift>+<space>",
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

