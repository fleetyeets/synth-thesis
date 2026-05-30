"""MIDI input listener — runs in a background thread."""

import threading
import rtmidi
from config import binding_key


class MidiListener:
    def __init__(self, mappings: dict, on_event=None, on_port_change=None):
        """
        mappings: live dict of {binding_key: Mapping} — checked at event time
        on_event: callback(midi_type, channel, number, trigger, velocity, binding_k)
        on_port_change: callback(port_name or None) when device connects/disconnects
        """
        self.mappings = mappings
        self.on_event = on_event
        self.on_port_change = on_port_change
        self._midi_in = None
        self._running = False
        self._thread = None
        self._port_name = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._midi_in:
            self._midi_in.close_port()

    def _open_port(self):
        ports = self._midi_in.get_ports()
        for i, name in enumerate(ports):
            if "MPK" in name or "mpk" in name.lower():
                self._midi_in.open_port(i)
                self._port_name = name
                if self.on_port_change:
                    self.on_port_change(name)
                return True
        # fallback: open first available
        if ports:
            self._midi_in.open_port(0)
            self._port_name = ports[0]
            if self.on_port_change:
                self.on_port_change(ports[0])
            return True
        return False

    def _run(self):
        import time
        self._midi_in = rtmidi.MidiIn()
        self._midi_in.ignore_types(sysex=True, timing=True, active_sense=True)

        connected = self._open_port()
        if not connected and self.on_port_change:
            self.on_port_change(None)

        while self._running:
            msg = self._midi_in.get_message()
            if msg:
                data, _ = msg
                self._dispatch(data)
            else:
                # detect disconnect
                ports = self._midi_in.get_ports()
                if not ports and self._port_name:
                    self._port_name = None
                    if self.on_port_change:
                        self.on_port_change(None)
                time.sleep(0.001)

    def _dispatch(self, data: list):
        status = data[0]
        msg_type = status & 0xF0
        channel = status & 0x0F

        if msg_type == 0x90 and len(data) >= 3:   # note on
            note, vel = data[1], data[2]
            trigger = "on" if vel > 0 else "off"
            self._fire("note", channel, note, trigger, vel)
            self._fire("note", channel, note, "any", vel)

        elif msg_type == 0x80 and len(data) >= 3:  # note off
            note, vel = data[1], data[2]
            self._fire("note", channel, note, "off", vel)
            self._fire("note", channel, note, "any", vel)

        elif msg_type == 0xB0 and len(data) >= 3:  # CC
            cc, val = data[1], data[2]
            self._fire("cc", channel, cc, "change", val)

        elif msg_type == 0xE0 and len(data) >= 3:  # pitch wheel
            val = ((data[2] << 7) | data[1]) - 8192
            self._fire("pitchwheel", channel, 0, "change", val)

    def _fire(self, midi_type, channel, number, trigger, velocity):
        key = binding_key(midi_type, channel, number, trigger)
        mapping = self.mappings.get(key)
        if self.on_event:
            self.on_event(midi_type, channel, number, trigger, velocity, key, mapping)
