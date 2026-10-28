"""
Global hotkey listener using pynput.
Supports Hold-to-Talk (Push-to-Talk) and Toggle-to-Talk (Hands-Free) modes.
"""
from typing import Callable, Optional, Set
from pynput import keyboard


def normalize_key(key) -> Optional[str]:
    """Normalize pynput Key / KeyCode into a clean token."""
    if key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r):
        return "alt"
    if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
        return "win"
    if key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
        return "ctrl"
    if key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
        return "shift"
    if key == keyboard.Key.space:
        return "space"
    if key == keyboard.Key.caps_lock:
        return "caps_lock"

    # Named special keys like f1-f12
    if isinstance(key, keyboard.Key):
        return key.name.lower()

    # Character keys
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.lower()
        if key.vk:
            # Common VK code fallbacks
            return f"vk_{key.vk}"

    return None


def parse_hotkey_string(hotkey_str: str) -> Set[str]:
    """Parse hotkey string like '<alt>+<space>' or 'alt+space' into a set of tokens."""
    tokens = set()
    cleaned = hotkey_str.replace("<", "").replace(">", "").strip().lower()
    for part in cleaned.split("+"):
        part = part.strip()
        if part in ("cmd", "win", "windows", "super"):
            tokens.add("win")
        elif part in ("alt", "option"):
            tokens.add("alt")
        elif part in ("ctrl", "control"):
            tokens.add("ctrl")
        elif part in ("shift",):
            tokens.add("shift")
        elif part in ("space", "spacebar"):
            tokens.add("space")
        elif part:
            tokens.add(part)
    return tokens


class HotkeyListener:
    def __init__(
        self,
        hotkey_hold_str: str = "<alt>+<space>",
        hotkey_toggle_str: str = "<alt>+<shift>+<space>",
        on_start_record: Optional[Callable[[str], None]] = None,  # mode: "hold" or "toggle"
        on_stop_record: Optional[Callable[[str], None]] = None,
    ):
        self.hold_keys: Set[str] = parse_hotkey_string(hotkey_hold_str)
        self.toggle_keys: Set[str] = parse_hotkey_string(hotkey_toggle_str)
        self.on_start_record = on_start_record
        self.on_stop_record = on_stop_record

        self.currently_pressed: Set[str] = set()
        self.active_mode: Optional[str] = None  # None, "hold", or "toggle"
        self._toggle_pressed = False
        self._listener: Optional[keyboard.Listener] = None

    def update_hotkeys(self, hold_str: str, toggle_str: str):
        """Update hotkey combinations dynamically."""
        self.hold_keys = parse_hotkey_string(hold_str)
        self.toggle_keys = parse_hotkey_string(toggle_str)
        print(f"[HotkeyListener] Updated Hold: {self.hold_keys}, Toggle: {self.toggle_keys}")

    def start(self):
        """Start global keyboard listener."""
        if self._listener is not None:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        print(f"[HotkeyListener] Started listening. Hold: {self.hold_keys}, Toggle: {self.toggle_keys}")

    def stop(self):
        """Stop global keyboard listener."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key):
        token = normalize_key(key)
        if not token:
            return

        self.currently_pressed.add(token)

        # 1. Check Toggle Hotkey first (usually more specific, e.g. 3 keys vs 2 keys)
        if self.toggle_keys and self.toggle_keys.issubset(self.currently_pressed):
            if not self._toggle_pressed:
                self._toggle_pressed = True
                if self.active_mode == "toggle":
                    # Currently in toggle recording -> STOP
                    self.active_mode = None
                    if self.on_stop_record:
                        self.on_stop_record("toggle")
                elif self.active_mode is None:
                    # Not recording -> START toggle
                    self.active_mode = "toggle"
                    if self.on_start_record:
                        self.on_start_record("toggle")
            return

        # 2. Check Hold Hotkey (Push-to-Talk)
        if self.hold_keys and self.hold_keys.issubset(self.currently_pressed):
            if self.active_mode is None:
                self.active_mode = "hold"
                if self.on_start_record:
                    self.on_start_record("hold")
            return

    def _on_release(self, key):
        token = normalize_key(key)
        if not token:
            return

        self.currently_pressed.discard(token)

        # Reset toggle fired latch when any toggle key is released
        if self.toggle_keys and token in self.toggle_keys:
            self._toggle_pressed = False

        # If we were in "hold" mode and one of the hold keys is released -> STOP
        if self.active_mode == "hold" and token in self.hold_keys:
            self.active_mode = None
            # Dismiss any Windows Alt-menu activation if Alt or Win was involved
            if "alt" in self.hold_keys or "win" in self.hold_keys:
                try:
                    import ctypes
                    # Send Escape keyup/down to ensure menu bars are dismissed
                    ctypes.windll.user32.keybd_event(0x1B, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0x1B, 0, 2, 0)
                except Exception:
                    pass

            if self.on_stop_record:
                self.on_stop_record("hold")

