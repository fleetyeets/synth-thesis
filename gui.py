"""synth-thesis — MIDI → action mapper GUI."""

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import threading
import time
from pynput import keyboard as kb_module

import config
import actions
from config import Action, Mapping, binding_key, control_label
from midi_listener import MidiListener

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── colours ──────────────────────────────────────────────────────────────────
BG       = "#1a1a2e"
PANEL    = "#16213e"
ACCENT   = "#0f3460"
HIGHLIGHT= "#e94560"
TEXT     = "#eaeaea"
DIM      = "#888888"
GREEN    = "#4ade80"
AMBER    = "#fbbf24"

FLASH_MS = 120   # how long a control flashes on activity


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("synth-thesis")
        self.geometry("920x680")
        self.configure(fg_color=BG)
        self.resizable(True, True)

        self.mappings: dict[str, Mapping] = config.load()
        self._learn_pending: dict | None = None   # waiting for next MIDI event
        self._flash_timers: dict[str, str] = {}   # binding_key → after id

        self._build_ui()

        self.listener = MidiListener(
            mappings=self.mappings,
            on_event=self._on_midi,
            on_port_change=self._on_port_change,
        )
        self.listener.start()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # top bar
        top = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, height=54)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)

        ctk.CTkLabel(top, text="synth-thesis", font=("Courier New", 20, "bold"),
                     text_color=HIGHLIGHT).pack(side="left", padx=18, pady=12)

        self.status_dot = ctk.CTkLabel(top, text="●", font=("Courier New", 14),
                                       text_color=DIM)
        self.status_dot.pack(side="left", padx=(0, 4))
        self.status_label = ctk.CTkLabel(top, text="no device", font=("Courier New", 12),
                                          text_color=DIM)
        self.status_label.pack(side="left")

        # learn button (top right)
        self.learn_btn = ctk.CTkButton(
            top, text="[ LEARN ]", width=110, height=32,
            font=("Courier New", 13, "bold"),
            fg_color=ACCENT, hover_color=HIGHLIGHT,
            command=self._start_learn,
        )
        self.learn_btn.pack(side="right", padx=18, pady=10)

        # learn status bar (hidden by default)
        self.learn_bar = ctk.CTkFrame(self, fg_color=HIGHLIGHT, corner_radius=0, height=34)
        self.learn_label = ctk.CTkLabel(self.learn_bar,
                                         text="Press any key, pad, or knob on the MPK mini…",
                                         font=("Courier New", 12), text_color="white")
        self.learn_label.pack(side="left", padx=16)
        ctk.CTkButton(self.learn_bar, text="✕ cancel", width=70, height=24,
                      font=("Courier New", 11), fg_color="#c0392b", hover_color="#e74c3c",
                      command=self._cancel_learn).pack(side="right", padx=10)

        # main content split
        content = ctk.CTkFrame(self, fg_color=BG)
        content.pack(fill="both", expand=True, padx=12, pady=(8, 12))

        # left: live activity feed
        left = ctk.CTkFrame(content, fg_color=PANEL, corner_radius=10, width=280)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        ctk.CTkLabel(left, text="LIVE MIDI", font=("Courier New", 11, "bold"),
                     text_color=DIM).pack(anchor="w", padx=12, pady=(10, 4))

        self.activity_box = ctk.CTkTextbox(left, font=("Courier New", 11),
                                            fg_color="#0d0d1a", text_color=GREEN,
                                            state="disabled", wrap="none")
        self.activity_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # right: mappings table
        right = ctk.CTkFrame(content, fg_color=PANEL, corner_radius=10)
        right.pack(side="left", fill="both", expand=True)

        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(hdr, text="MAPPINGS", font=("Courier New", 11, "bold"),
                     text_color=DIM).pack(side="left")

        self.mapping_scroll = ctk.CTkScrollableFrame(right, fg_color="transparent",
                                                      label_text="")
        self.mapping_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._refresh_mapping_list()

    # ── learn flow ────────────────────────────────────────────────────────────

    def _start_learn(self):
        self._learn_pending = {}
        self.learn_bar.pack(fill="x", side="top", before=self.learn_bar.master.winfo_children()[2]
                            if len(self.learn_bar.master.winfo_children()) > 2 else None)
        self.learn_bar.pack(fill="x")
        self.learn_btn.configure(state="disabled")

    def _cancel_learn(self):
        self._learn_pending = None
        self.learn_bar.pack_forget()
        self.learn_btn.configure(state="normal")

    def _complete_learn(self, midi_type, channel, number, trigger, velocity):
        """Called when we captured a MIDI event during learn mode."""
        self._learn_pending = None
        self.learn_bar.pack_forget()
        self.learn_btn.configure(state="normal")
        self._open_bind_dialog(midi_type, channel, number, trigger)

    # ── binding dialog ────────────────────────────────────────────────────────

    def _open_bind_dialog(self, midi_type, channel, number, trigger=None):
        key_prefix = f"{midi_type}:{channel}:{number}"
        existing = {k: v for k, v in self.mappings.items()
                    if k.startswith(key_prefix)}

        dlg = ctk.CTkToplevel(self)
        dlg.title("Bind Control")
        dlg.geometry("520x560")
        dlg.configure(fg_color=BG)
        dlg.grab_set()
        dlg.lift()
        dlg.focus_force()

        clabel = control_label(midi_type, channel, number)
        ctk.CTkLabel(dlg, text=clabel, font=("Courier New", 15, "bold"),
                     text_color=HIGHLIGHT).pack(pady=(18, 4))

        # trigger selector (only relevant for notes)
        trigger_var = ctk.StringVar(value=trigger or "on")
        if midi_type == "note":
            tf = ctk.CTkFrame(dlg, fg_color="transparent")
            tf.pack(pady=(0, 8))
            ctk.CTkLabel(tf, text="Trigger on:", font=("Courier New", 11),
                         text_color=TEXT).pack(side="left", padx=(0, 8))
            for t in ("on", "off", "any"):
                ctk.CTkRadioButton(tf, text=t, variable=trigger_var, value=t,
                                   font=("Courier New", 11)).pack(side="left", padx=4)
        else:
            trigger_var.set("change")

        # control name
        name_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        name_frame.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkLabel(name_frame, text="Label (optional):", font=("Courier New", 11),
                     text_color=DIM).pack(anchor="w")
        existing_name = next(iter(existing.values())).name if existing else ""
        name_entry = ctk.CTkEntry(name_frame, placeholder_text="e.g. Pad 1, Knob 3",
                                   font=("Courier New", 12))
        name_entry.pack(fill="x")
        if existing_name:
            name_entry.insert(0, existing_name)

        # action type
        type_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        type_frame.pack(fill="x", padx=24, pady=(0, 4))
        ctk.CTkLabel(type_frame, text="Action type:", font=("Courier New", 11),
                     text_color=DIM).pack(anchor="w")
        existing_action = next(iter(existing.values())).action if existing else None
        action_type_var = ctk.StringVar(value=existing_action.type if existing_action else "launch_app")
        type_menu = ctk.CTkOptionMenu(type_frame, variable=action_type_var,
                                       values=config.ACTION_TYPES,
                                       font=("Courier New", 12),
                                       command=lambda _: _update_hint())
        type_menu.pack(fill="x")

        # value entry
        val_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        val_frame.pack(fill="x", padx=24, pady=(0, 2))
        ctk.CTkLabel(val_frame, text="Value:", font=("Courier New", 11),
                     text_color=DIM).pack(anchor="w")

        val_row = ctk.CTkFrame(val_frame, fg_color="transparent")
        val_row.pack(fill="x")
        val_entry = ctk.CTkEntry(val_row, font=("Courier New", 12), height=36)
        val_entry.pack(side="left", fill="x", expand=True)
        if existing_action:
            val_entry.insert(0, existing_action.value)

        record_btn = ctk.CTkButton(val_row, text="⏺ Record", width=90, height=36,
                                    font=("Courier New", 11), fg_color=ACCENT,
                                    hover_color=HIGHLIGHT,
                                    command=lambda: _start_record())
        record_btn.pack(side="left", padx=(6, 0))
        record_btn.pack_forget()  # hidden until keystroke type selected

        hint_label = ctk.CTkLabel(dlg, text="", font=("Courier New", 10),
                                   text_color=DIM, wraplength=460)
        hint_label.pack(padx=24, anchor="w")

        HINTS = {
            "launch_app":   "App name as shown in /Applications — e.g. 'Spotify', 'Terminal'",
            "shell":        "Any shell command. Use {value} (0-127) or {pct} (0-100) for knob position.",
            "url":          "Full URL — e.g. 'https://example.com'",
            "applescript":  "Inline AppleScript. Use {value} or {pct} — e.g. 'set volume output volume {pct}'",
            "keystroke":    "Keys joined by + — or click ⏺ Record and press the shortcut",
            "volume":       "Maps knob position directly to system output volume. No value needed.",
        }

        _kb_listener: list = [None]

        MOD_MAP = {
            kb_module.Key.cmd:     "cmd",  kb_module.Key.cmd_l:   "cmd",  kb_module.Key.cmd_r:   "cmd",
            kb_module.Key.ctrl:    "ctrl", kb_module.Key.ctrl_l:  "ctrl", kb_module.Key.ctrl_r:  "ctrl",
            kb_module.Key.alt:     "alt",  kb_module.Key.alt_l:   "alt",  kb_module.Key.alt_r:   "alt",
            kb_module.Key.shift:   "shift",kb_module.Key.shift_l: "shift",kb_module.Key.shift_r: "shift",
        }
        _held_mods: set = set()

        def _start_record():
            _held_mods.clear()
            record_btn.configure(text="● listening…", state="disabled", fg_color=HIGHLIGHT)
            hint_label.configure(text="Press your shortcut now…")

            def on_press(key):
                if key in MOD_MAP:
                    _held_mods.add(MOD_MAP[key])
                    return
                # non-modifier — capture combo
                if hasattr(key, "char") and key.char:
                    final = key.char.lower()
                elif hasattr(key, "name") and key.name:
                    final = key.name.lower()
                else:
                    return
                parts = [m for m in ("cmd", "ctrl", "alt", "shift") if m in _held_mods]
                parts.append(final)
                combo = "+".join(parts)
                dlg.after(0, lambda: _fill_combo(combo))
                return False  # stop listener

            def on_release(key):
                _held_mods.discard(MOD_MAP.get(key, ""))

            listener = kb_module.Listener(on_press=on_press, on_release=on_release)
            listener.daemon = True
            listener.start()
            _kb_listener[0] = listener

        def _fill_combo(combo: str):
            val_entry.delete(0, "end")
            val_entry.insert(0, combo)
            record_btn.configure(text="⏺ Record", state="normal", fg_color=ACCENT)
            hint_label.configure(text=HINTS["keystroke"])
            if _kb_listener[0]:
                _kb_listener[0].stop()
                _kb_listener[0] = None

        def _update_hint(*_):
            hint_label.configure(text=HINTS.get(action_type_var.get(), ""))
            if action_type_var.get() == "keystroke":
                record_btn.pack(side="left", padx=(6, 0))
            else:
                record_btn.pack_forget()
                if _kb_listener[0]:
                    _kb_listener[0].stop()
                    _kb_listener[0] = None

        _update_hint()

        # browse button for launch_app
        browse_btn = ctk.CTkButton(dlg, text="Browse app…", width=110,
                                    font=("Courier New", 11), fg_color=ACCENT,
                                    command=lambda: _browse())
        browse_btn.pack(anchor="e", padx=24)

        def _browse():
            path = filedialog.askopenfilename(
                initialdir="/Applications",
                title="Choose an application",
                filetypes=[("Applications", "*.app"), ("All files", "*.*")],
            )
            if path:
                name = path.split("/")[-1].replace(".app", "")
                val_entry.delete(0, "end")
                val_entry.insert(0, name)

        action_type_var.trace_add("write", lambda *_: browse_btn.configure(
            state="normal" if action_type_var.get() == "launch_app" else "disabled"
        ))

        dlg.protocol("WM_DELETE_WINDOW", lambda: (
            _kb_listener[0].stop() if _kb_listener[0] else None, dlg.destroy()
        ))

        # label entry
        lbl_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        lbl_frame.pack(fill="x", padx=24, pady=(8, 0))
        ctk.CTkLabel(lbl_frame, text="Display label (optional):",
                     font=("Courier New", 11), text_color=DIM).pack(anchor="w")
        lbl_entry = ctk.CTkEntry(lbl_frame, font=("Courier New", 12))
        lbl_entry.pack(fill="x")
        if existing_action and existing_action.label:
            lbl_entry.insert(0, existing_action.label)

        # buttons
        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", padx=24, pady=16)

        def _save():
            val = val_entry.get().strip()
            if not val and action_type_var.get() != "volume":
                messagebox.showerror("Missing value", "Enter a value for the action.")
                return
            act = Action(
                type=action_type_var.get(),
                value=val,
                label=lbl_entry.get().strip(),
            )
            trig = trigger_var.get()
            key = binding_key(midi_type, channel, number, trig)
            self.mappings[key] = Mapping(
                midi_type=midi_type,
                channel=channel,
                number=number,
                trigger=trig,
                action=act,
                name=name_entry.get().strip(),
            )
            config.save(self.mappings)
            self._refresh_mapping_list()
            dlg.destroy()

        def _delete():
            trig = trigger_var.get()
            key = binding_key(midi_type, channel, number, trig)
            if key in self.mappings:
                del self.mappings[key]
                config.save(self.mappings)
                self._refresh_mapping_list()
            dlg.destroy()

        ctk.CTkButton(btn_row, text="Save", font=("Courier New", 13, "bold"),
                      fg_color=GREEN, text_color="#000", hover_color="#22c55e",
                      command=_save).pack(side="left", expand=True, padx=(0, 6))
        ctk.CTkButton(btn_row, text="Delete", font=("Courier New", 13),
                      fg_color="#7f1d1d", hover_color="#991b1b",
                      command=_delete).pack(side="left", expand=True, padx=(6, 0))

    # ── mapping list ──────────────────────────────────────────────────────────

    def _refresh_mapping_list(self):
        for w in self.mapping_scroll.winfo_children():
            w.destroy()

        if not self.mappings:
            ctk.CTkLabel(self.mapping_scroll,
                         text="No mappings yet.\nHit [ LEARN ] and press a key or pad.",
                         font=("Courier New", 12), text_color=DIM,
                         justify="center").pack(pady=40)
            return

        for key, m in sorted(self.mappings.items()):
            row = ctk.CTkFrame(self.mapping_scroll, fg_color=ACCENT, corner_radius=8)
            row.pack(fill="x", pady=3)

            left_col = ctk.CTkFrame(row, fg_color="transparent")
            left_col.pack(side="left", fill="both", expand=True, padx=10, pady=8)

            ctrl_name = m.name or control_label(m.midi_type, m.channel, m.number)
            trig_suffix = f" [{m.trigger}]" if m.midi_type == "note" else ""
            ctk.CTkLabel(left_col,
                         text=ctrl_name + trig_suffix,
                         font=("Courier New", 12, "bold"),
                         text_color=TEXT, anchor="w").pack(anchor="w")

            action_text = m.action.label or m.action.value
            type_badge = f"[{m.action.type}]"
            ctk.CTkLabel(left_col,
                         text=f"{type_badge}  {action_text}",
                         font=("Courier New", 10),
                         text_color=DIM, anchor="w").pack(anchor="w")

            # flash indicator dot
            dot = ctk.CTkLabel(row, text="●", font=("Courier New", 14),
                               text_color=DIM, width=24)
            dot.pack(side="right", padx=(0, 6))
            row._flash_dot = dot

            edit_btn = ctk.CTkButton(
                row, text="edit", width=50, height=28,
                font=("Courier New", 11), fg_color="#1e3a5f", hover_color=HIGHLIGHT,
                command=lambda mm=m: self._open_bind_dialog(mm.midi_type, mm.channel, mm.number),
            )
            edit_btn.pack(side="right", padx=4, pady=6)

            row._binding_key = key
            self._flash_timers[key] = None

    # ── MIDI callbacks ────────────────────────────────────────────────────────

    def _on_midi(self, midi_type, channel, number, trigger, velocity, bkey, mapping):
        # execute if mapped
        if mapping:
            actions.run(mapping.action, velocity)

        # learn mode intercept
        if self._learn_pending is not None:
            # only capture "on" / "change" events for learning, not note-off
            if trigger in ("on", "change", "any") and velocity != 0:
                self.after(0, self._complete_learn,
                           midi_type, channel, number, trigger, velocity)

        # update activity log + flash
        self.after(0, self._update_activity, midi_type, channel, number, trigger, velocity, bkey)

    def _update_activity(self, midi_type, channel, number, trigger, velocity, bkey):
        label = control_label(midi_type, channel, number)
        line = f"{label}  {trigger}  v={velocity}\n"
        self.activity_box.configure(state="normal")
        self.activity_box.insert("end", line)
        self.activity_box.see("end")
        # keep last 200 lines
        lines = int(self.activity_box.index("end-1c").split(".")[0])
        if lines > 200:
            self.activity_box.delete("1.0", f"{lines-200}.0")
        self.activity_box.configure(state="disabled")

        # flash the row dot
        self._flash_row(bkey)

    def _flash_row(self, bkey):
        # find matching row in scroll frame
        for row in self.mapping_scroll.winfo_children():
            if getattr(row, "_binding_key", None) == bkey:
                dot = getattr(row, "_flash_dot", None)
                if dot:
                    dot.configure(text_color=HIGHLIGHT)
                    if self._flash_timers.get(bkey):
                        self.after_cancel(self._flash_timers[bkey])
                    self._flash_timers[bkey] = self.after(
                        FLASH_MS, lambda d=dot: d.configure(text_color=DIM)
                    )

    def _on_port_change(self, port_name):
        self.after(0, self._update_status, port_name)

    def _update_status(self, port_name):
        if port_name:
            self.status_dot.configure(text_color=GREEN)
            self.status_label.configure(text=port_name, text_color=GREEN)
        else:
            self.status_dot.configure(text_color=DIM)
            self.status_label.configure(text="no device", text_color=DIM)

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def _on_close(self):
        self.listener.stop()
        self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
