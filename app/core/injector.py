"""
Text injection subsystem for Windows.
Pastes or types text directly into whichever window is currently active.
Includes clipboard retry logic, safe retention so transcripts are never lost,
and graceful fallback to simulated typing.
"""
import ctypes
import time
from typing import Optional
import pyperclip

# Windows Virtual Key codes
VK_CONTROL = 0x11
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002


def send_paste_event():
    """Send native Windows Ctrl+V keystrokes via user32.keybd_event."""
    try:
        user32 = ctypes.windll.user32
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        time.sleep(0.02)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    except Exception as e:
        print(f"[TextInjector] send_paste_event error: {e}")


class TextInjector:
    def __init__(self, method: str = "clipboard", restore_clipboard: bool = False):
        self.method = method  # "clipboard" or "typing"
        self.restore_clipboard = restore_clipboard
        self.last_transcript: Optional[str] = None

    def inject(self, text: str) -> bool:
        """
        Inject text into the currently active target window.
        Returns True on success.
        Guarantees that the transcribed text is stored in the clipboard so it never vanishes,
        even if no text box was focused.
        """
        if not text:
            return False

        clean_text = text.strip()
        if not clean_text:
            return False

        self.last_transcript = clean_text
        payload = clean_text + " "

        # Always copy the transcript to clipboard first so it is never lost
        try:
            pyperclip.copy(clean_text)
        except Exception as e:
            print(f"[TextInjector] Clipboard copy warning: {e}")

        if self.method == "clipboard":
            success = self._inject_via_clipboard(payload)
            if not success:
                print("[TextInjector] Clipboard injection failed; falling back to typing.")
                return self._inject_via_typing(payload)
            return True
        else:
            return self._inject_via_typing(payload)

    def _inject_via_clipboard(self, text: str) -> bool:
        """Copy target text to clipboard, send Ctrl+V, and keep it safe on clipboard."""
        previous_clipboard: Optional[str] = None
        if self.restore_clipboard:
            for _ in range(3):
                try:
                    previous_clipboard = pyperclip.paste()
                    break
                except Exception:
                    time.sleep(0.03)

        copied = False
        for _ in range(3):
            try:
                pyperclip.copy(text)
                copied = True
                break
            except Exception:
                time.sleep(0.04)

        if not copied:
            return False

        time.sleep(0.03)
        send_paste_event()
        time.sleep(0.08)

        # Only restore old clipboard if explicitly requested (default is False so speech is never lost)
        if self.restore_clipboard and previous_clipboard is not None:
            try:
                pyperclip.copy(previous_clipboard)
            except Exception:
                pass
        else:
            try:
                pyperclip.copy(text.strip())
            except Exception:
                pass

        return True

    def _inject_via_typing(self, text: str) -> bool:
        """Simulate direct typing into the active window while preserving clipboard safety."""
        try:
            pyperclip.copy(text.strip())
        except Exception:
            pass

        try:
            import pyautogui
            pyautogui.write(text, interval=0.005)
            return True
        except Exception:
            try:
                from pynput.keyboard import Controller
                kb = Controller()
                kb.type(text)
                return True
            except Exception as e:
                print(f"[TextInjector] All injection methods failed: {e}")
                return False
