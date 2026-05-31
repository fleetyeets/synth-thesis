"""Execute mapped actions."""

import os
import shutil
import subprocess
import threading
import webbrowser
from pynput.keyboard import Controller, Key, HotKey

_keyboard = Controller()
_volume_prev_cc:     int | None = None
_brightness_prev_cc: int | None = None

# Maps string token → pynput Key constant
SPECIAL_KEYS = {
    "cmd": Key.cmd, "ctrl": Key.ctrl, "alt": Key.alt, "shift": Key.shift,
    "space": Key.space, "enter": Key.enter, "tab": Key.tab, "esc": Key.esc,
    "backspace": Key.backspace, "delete": Key.delete,
    "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
    "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
    "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
    "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
}


# macOS key codes for special keys — used for AppleScript keystroke dispatch,
# which is more reliable than pynput for system-level shortcuts (Mission Control, etc.)
_AS_KEYCODES = {
    "right": 124, "left": 123, "up": 126, "down": 125,
    "f1": 122, "f2": 120, "f3": 99,  "f4": 118, "f5": 96,
    "f6": 97,  "f7": 98,  "f8": 100, "f9": 101, "f10": 109,
    "f11": 103,"f12": 111,
    "space": 49, "enter": 36, "tab": 48, "esc": 53,
    "backspace": 51, "delete": 117,
    "0": 29, "1": 18, "2": 19, "3": 20, "4": 21,
    "5": 23, "6": 22, "7": 26, "8": 28, "9": 25,
}

# DDPM (Dell Display) hotkeys for brightness — F1=down, F2=up
_BRIGHTNESS_STEP_KEY_UP   = "f2"
_BRIGHTNESS_STEP_KEY_DOWN = "f1"
_AS_MODS = {
    "cmd": "command down",
    "ctrl": "control down",
    "alt": "option down",
    "shift": "shift down",
}


def _send_keystroke(ks: str):
    parts = [p.strip().lower() for p in ks.split("+")]
    final = parts[-1]
    mods = [_AS_MODS[p] for p in parts[:-1] if p in _AS_MODS]
    mod_str = "{" + ", ".join(mods) + "}" if mods else ""

    if final in _AS_KEYCODES:
        # arrow keys, F-keys, etc. — must use key code for system shortcuts
        using = f" using {mod_str}" if mod_str else ""
        script = f'tell application "System Events" to key code {_AS_KEYCODES[final]}{using}'
    else:
        # printable character
        using = f" using {mod_str}" if mod_str else ""
        script = f'tell application "System Events" to keystroke "{final}"{using}'

    subprocess.run(["osascript", "-e", script], capture_output=True)


def run(action, velocity: int = 127):
    """Run an action in a background thread (non-blocking)."""
    threading.Thread(target=_execute, args=(action, velocity), daemon=True).start()


def _resolve(template: str, velocity: int) -> str:
    """Substitute {value} (raw 0-127) and {pct} (0-100 scaled) in action strings."""
    pct = round(velocity * 100 / 127)
    return template.replace("{value}", str(velocity)).replace("{pct}", str(pct))


def _execute(action, velocity: int):
    try:
        if action.type == "brightness":
            global _brightness_prev_cc
            if velocity == 0:
                return
            prev = _brightness_prev_cc
            _brightness_prev_cc = velocity
            if prev is None:
                return
            raw_delta = velocity - prev
            step_delta = round(raw_delta * 16 / 127)
            if step_delta == 0 and raw_delta != 0:
                step_delta = 1 if raw_delta > 0 else -1
            key = Key.f2 if step_delta > 0 else Key.f1
            for _ in range(abs(step_delta)):
                _keyboard.press(key)
                _keyboard.release(key)
            return

        if action.type == "volume":
            global _volume_prev_cc
            if velocity == 0:
                return
            prev = _volume_prev_cc
            _volume_prev_cc = velocity
            if prev is None:
                return
            # knob delta → volume key presses; scale 127 CC range to 16 OS steps
            raw_delta = velocity - prev
            step_delta = round(raw_delta * 16 / 127)
            # guarantee at least one press if knob actually moved
            if step_delta == 0 and raw_delta != 0:
                step_delta = 1 if raw_delta > 0 else -1
            key = Key.media_volume_up if step_delta > 0 else Key.media_volume_down
            for _ in range(abs(step_delta)):
                _keyboard.press(key)
                _keyboard.release(key)
            return

        if action.type == "launch_app":
            val = action.value
            if val.endswith(".app") or val.startswith("/"):
                subprocess.Popen(["open", val])
            else:
                # try open -a first (app bundles in /Applications etc.)
                result = subprocess.run(["open", "-a", val], capture_output=True)
                if result.returncode != 0:
                    # resolve against the user's real PATH (includes ~/bin etc.)
                    user_path = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + \
                                os.path.expanduser("~/bin")
                    resolved = shutil.which(val, path=user_path)
                    if resolved:
                        subprocess.Popen([resolved])
                    else:
                        # last resort: let zsh resolve it
                        subprocess.Popen(["zsh", "-lc", val])

        elif action.type == "shell":
            subprocess.Popen(_resolve(action.value, velocity), shell=True)

        elif action.type == "url":
            webbrowser.open(action.value)

        elif action.type == "applescript":
            subprocess.Popen(["osascript", "-e", _resolve(action.value, velocity)])

        elif action.type == "keystroke":
            _send_keystroke(action.value)

    except Exception as e:
        print(f"[actions] error running {action}: {e}")
