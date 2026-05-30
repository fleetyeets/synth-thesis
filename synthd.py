#!/usr/bin/env python3
"""synth-thesis daemon — headless MIDI listener. No GUI required."""

import os
import sys
import time
import signal

import config
import actions
from midi_listener import MidiListener

MAPPINGS_PATH = config.CONFIG_PATH


def _on_midi(midi_type, channel, number, trigger, velocity, bkey, mapping):
    if mapping:
        actions.run(mapping.action, velocity)


def _on_port_change(port_name):
    if port_name:
        print(f"[synthd] connected: {port_name}", flush=True)
    else:
        print("[synthd] device disconnected", flush=True)


def main():
    print("[synthd] starting", flush=True)

    mappings = config.load()
    print(f"[synthd] loaded {len(mappings)} mapping(s)", flush=True)

    listener = MidiListener(
        mappings=mappings,
        on_event=_on_midi,
        on_port_change=_on_port_change,
    )
    listener.start()

    def _shutdown(sig, frame):
        print("[synthd] shutting down", flush=True)
        listener.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # watch mappings.json for changes and hot-reload
    last_mtime = os.path.getmtime(MAPPINGS_PATH) if os.path.exists(MAPPINGS_PATH) else 0
    while True:
        time.sleep(1)
        try:
            mtime = os.path.getmtime(MAPPINGS_PATH) if os.path.exists(MAPPINGS_PATH) else 0
            if mtime != last_mtime:
                last_mtime = mtime
                new = config.load()
                mappings.clear()
                mappings.update(new)
                print(f"[synthd] reloaded {len(mappings)} mapping(s)", flush=True)
        except Exception as e:
            print(f"[synthd] reload error: {e}", flush=True)


if __name__ == "__main__":
    main()
