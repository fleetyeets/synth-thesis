"""Mapping config: load/save MIDI → action bindings."""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "mappings.json")

ACTION_TYPES = [
    "launch_app",
    "shell",
    "url",
    "applescript",
    "keystroke",
    "volume",
    "brightness",
]


@dataclass
class Action:
    type: str           # one of ACTION_TYPES
    value: str          # app name, shell cmd, url, script, or keystroke string
    label: str = ""     # human-friendly display name


@dataclass
class Mapping:
    """A single MIDI control → action binding."""
    midi_type: str       # "note", "cc", "pitchwheel"
    channel: int
    number: int          # note number or CC number (0 for pitchwheel)
    trigger: str         # "on", "off", "any" (for notes); "change" (for CC/pw)
    action: Action
    name: str = ""       # user-assigned label for the control


def _serialize(obj):
    if isinstance(obj, Mapping):
        d = asdict(obj)
        return d
    return obj


def load() -> dict[str, Mapping]:
    """Returns {binding_key: Mapping}. binding_key = f"{type}:{ch}:{num}:{trigger}"."""
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH) as f:
        raw = json.load(f)
    result = {}
    for key, v in raw.items():
        action = Action(**v["action"])
        m = Mapping(
            midi_type=v["midi_type"],
            channel=v["channel"],
            number=v["number"],
            trigger=v["trigger"],
            action=action,
            name=v.get("name", ""),
        )
        result[key] = m
    return result


def save(mappings: dict[str, Mapping]):
    with open(CONFIG_PATH, "w") as f:
        json.dump({k: asdict(v) for k, v in mappings.items()}, f, indent=2)


def binding_key(midi_type: str, channel: int, number: int, trigger: str) -> str:
    return f"{midi_type}:{channel}:{number}:{trigger}"


def control_label(midi_type: str, channel: int, number: int) -> str:
    if midi_type == "note":
        names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = (number // 12) - 1
        name = names[number % 12]
        return f"Note {name}{octave} (ch{channel+1})"
    elif midi_type == "cc":
        return f"Knob/CC {number} (ch{channel+1})"
    elif midi_type == "pitchwheel":
        return f"Pitch Wheel (ch{channel+1})"
    return f"{midi_type}:{number}"
