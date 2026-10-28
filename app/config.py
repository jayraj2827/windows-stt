"""
Application configuration manager for STT Subsystem.
"""
import json
import os
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    "model_name": "small.en",
    "device": "cuda",
    "compute_type": "float16",
    "hotkey_hold": "<ctrl>+<space>",
    "hotkey_toggle": "<ctrl>+<shift>+<space>",
    "input_device_index": None,
    "injection_method": "clipboard",  # "clipboard" or "typing"
    "restore_clipboard": True,
    "overlay_enabled": True,
    "language": "en",
    "vad_filter": True,
    "sound_feedback": True,
}

CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")


def load_config() -> Dict[str, Any]:
    """Load configuration from disk, falling back to defaults."""
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                config.update(loaded)
        except Exception as e:
            print(f"[Config] Error loading {CONFIG_FILE}: {e}")
    else:
        save_config(config)
    return config


def save_config(config: Dict[str, Any]) -> None:
    """Save current configuration to disk."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"[Config] Error saving config: {e}")

