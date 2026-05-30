# synth-thesis

MIDI controller → system action mapper for macOS. Bind any key, pad, or knob on an Akai MPK mini (or other MIDI device) to launch apps, run shell commands, send keystrokes, control system volume, open URLs, or execute AppleScript.

Runs as a background daemon at boot via launchd. A GUI lets you configure mappings without touching any config files.

---

## Requirements

- macOS (arm64)
- Python 3.14+ (Homebrew)
- Akai MPK mini (or any CoreMIDI-compatible device)

```
brew install python@3.14 python-tk@3.14
pip3 install python-rtmidi customtkinter pynput --break-system-packages
```

---

## Structure

```
synth-thesis/
├── main.py           # GUI entry point
├── synthd.py         # Headless daemon (run at boot)
├── gui.py            # Configuration interface
├── midi_listener.py  # CoreMIDI input thread
├── actions.py        # Action executor
├── config.py         # Mapping schema + load/save
└── mappings.json     # Persisted bindings (auto-created)
```

---

## Running

**GUI** (configuration):
```
synth-thesis
```

**Daemon** (headless, mappings fire without GUI open):
```
python3 synthd.py
```

The daemon is installed as a LaunchAgent and starts automatically at login. It hot-reloads `mappings.json` within 1 second of any change saved from the GUI.

---

## LaunchAgent

The daemon is managed by launchd:

```
# Start
launchctl load ~/Library/LaunchAgents/com.allie.synth-thesis.plist

# Stop
launchctl unload ~/Library/LaunchAgents/com.allie.synth-thesis.plist

# Logs
tail -f ~/Library/Logs/synth-thesis.log
```

---

## Creating a Mapping

1. Open the GUI: `synth-thesis`
2. Click **[ LEARN ]**
3. Press any key, pad, or turn any knob on the MPK mini
4. Choose trigger (for notes: `on`, `off`, or `any`), action type, and value
5. Save — the daemon picks it up immediately

---

## Action Types

| Type | Value | Notes |
|------|-------|-------|
| `launch_app` | App name, e.g. `Spotify` | Searches /Applications; falls back to PATH |
| `shell` | Any shell command | Supports `{value}` and `{pct}` placeholders |
| `url` | Full URL | Opens in default browser |
| `applescript` | Inline AppleScript | Supports `{value}` and `{pct}` placeholders |
| `keystroke` | e.g. `cmd+shift+t` | Modifier keys: `cmd ctrl alt shift` |
| `volume` | *(none)* | Maps knob to system volume via HUD keys |

### Placeholders for knobs

In `shell` and `applescript` actions, you can use:
- `{value}` — raw CC value, 0–127
- `{pct}` — scaled to 0–100

Example AppleScript: `set volume output volume {pct}`

---

## MPK Mini Notes

- **Keys** (25 mini keys): note on/off, channel 0 or 9
- **Pads** (8 drum pads): note on/off, typically channel 9
- **Knobs** (8 knobs): CC messages, absolute 0–127
- **Transport buttons**: note or CC depending on preset

The live MIDI feed in the GUI shows every incoming event with type, note/CC number, channel, and velocity — useful for identifying what a control is sending before binding it.

---

## Adding to PATH

The launcher script lives at `~/bin/synth-thesis`. If `~/bin` is in your PATH, run the GUI from anywhere with `synth-thesis`.
