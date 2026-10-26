#!/usr/bin/env python3
"""Transparent sticky notes you type in, pinned to the desktop.

Each note is a text file in ~/.config/desktop-note/notes/ and saves as you type.
Enter continues a bullet or numbered list. Ctrl+click a link or path to open it.
Drag the top strip to move, the bottom-right corner to resize, right-click for menu.

Runs as a single background app; `note.py --toggle | --show | --hide | --new`
(or the org.gtk.Actions D-Bus interface) controls it. `--background` starts hidden.
"""
import json
import os
import re
import subprocess
import sys
import time

os.environ.setdefault("GDK_BACKEND", "x11")  # Wayland apps can't pin to the desktop

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango

CONF = os.path.expanduser("~/.config/desktop-note")
NOTES = os.path.join(CONF, "notes")
STATE = os.path.join(CONF, "state.json")

FIRST_NOTE = """\
• Type anything here, it saves by itself
• Enter starts the next bullet, Enter twice ends the list
• Ctrl+click a link or path to open it: ~/Desktop
• Right-click for New note, text size, list style
"""

LIST_RE = re.compile(r"^(\s*)(•|-|\*|\d+\.)\s+")
LINK_RE = re.compile(r"(https?://\S+|~/\S*|/(?:[\w.-]+/)*[\w.-]+)")

CSS = b"""
window { background-color: transparent; }
#card { background-color: rgba(18, 18, 22, 0.32); border-radius: 14px; }
#grip { color: rgba(255,255,255,0.45); padding: 4px 0 0 0; }
textview, textview text { background-color: transparent; color: rgba(255,255,255,0.95);
                          caret-color: #ffd666; }
textview text selection { background-color: rgba(255,214,102,0.35); }
"""


def read_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def write_state(state):
    try:
        with open(STATE, "w") as f:
            json.dump(state, f, indent=1)
    except OSError:
        pass


def open_target(word):
    target = os.path.expanduser(word.rstrip(".,;:)"))
    if target.startswith(("http://", "https://")) or os.path.exists(target):
        env = dict(os.environ)
        env.pop("GDK_BACKEND", None)  # let opened apps run natively on Wayland
        subprocess.Popen(["xdg-open", target], env=env, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    return False


class Note(Gtk.Window):
    def __init__(self, app, note_id, geo):
        super().__init__(title="Desktop Note")
        self.app, self.id = app, note_id
        self.path = os.path.join(NOTES, f"{note_id}.txt")
        self.font = geo.get("font", 12)
        self.save_id = 0

        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.stick()
        self.set_default_size(geo.get("w", 300), geo.get("h", 220))
        self.move(geo.get("x", 60), geo.get("y", 80))

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.set_name("card")
        self.add(card)

        grip = Gtk.EventBox()
        grip_label = Gtk.Label(label="• • •")
        grip_label.set_name("grip")
        grip.add(grip_label)
        grip.connect("button-press-event", self.on_grip)
        grip.connect("realize", lambda w: w.get_window().set_cursor(
            Gdk.Cursor.new_from_name(w.get_display(), "move")))
        card.pack_start(grip, False, False, 0)

        self.view = Gtk.TextView()
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.set_left_margin(14)
        self.view.set_right_margin(14)
        self.view.set_top_margin(2)
        self.view.set_bottom_margin(10)
        self.font_css = Gtk.CssProvider()
        self.view.get_style_context().add_provider(self.font_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self.apply_font()
        self.view.connect("key-press-event", self.on_key)
        self.view.connect("button-press-event", self.on_click)
        self.view.connect("populate-popup", self.on_popup)

        self.buf = self.view.get_buffer()
        self.link_tag = self.buf.create_tag("link", underline=Pango.Underline.SINGLE,
                                            foreground="#8ec5ff")
        try:
            with open(self.path) as f:
                self.buf.set_text(f.read())
        except OSError:
            self.buf.set_text("• ")
        self.highlight()
        self.buf.connect("changed", self.on_changed)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.view)
        card.pack_start(scroll, True, True, 0)

        corner = Gtk.EventBox()
        corner.add(Gtk.Label(label="◢", xalign=1))
        corner.set_halign(Gtk.Align.END)
        corner.set_opacity(0.35)
        corner.connect("button-press-event", self.on_corner)
        corner.connect("realize", lambda w: w.get_window().set_cursor(
            Gdk.Cursor.new_from_name(w.get_display(), "se-resize")))
        card.pack_start(corner, False, False, 0)

        self.connect("configure-event", self.on_configure)
        self.connect("delete-event", lambda *_: self.hide() or True)
        card.show_all()

    # --- text ---------------------------------------------------------------
    def apply_font(self):
        self.font_css.load_from_data(f"textview {{ font-size: {self.font}pt; }}".encode())

    def on_changed(self, _buf):
        self.highlight()
        if self.save_id:
            GLib.source_remove(self.save_id)
        self.save_id = GLib.timeout_add(400, self.save)

    def save(self):
        self.save_id = 0
        text = self.buf.get_text(self.buf.get_start_iter(), self.buf.get_end_iter(), False)
        with open(self.path, "w") as f:
            f.write(text)
        return False

    def highlight(self):
        start, end = self.buf.get_bounds()
        self.buf.remove_tag(self.link_tag, start, end)
        text = self.buf.get_text(start, end, False)
        for m in LINK_RE.finditer(text):
            if m.start() > 0 and not text[m.start() - 1].isspace():
                continue
            self.buf.apply_tag(self.link_tag, self.buf.get_iter_at_offset(m.start()),
                               self.buf.get_iter_at_offset(m.end()))

    def current_line(self):
        it = self.buf.get_iter_at_mark(self.buf.get_insert())
        start = it.copy()
        start.set_line_offset(0)
        end = it.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        return start, end, self.buf.get_text(start, end, False)

    def on_key(self, _view, event):
        if event.keyval not in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) or event.state & Gdk.ModifierType.SHIFT_MASK:
            return False
        start, end, line = self.current_line()
        m = LIST_RE.match(line)
        if not m:
            return False
        if not line[m.end():].strip():  # empty bullet: end the list
            self.buf.delete(start, end)
            return True
        indent, marker = m.group(1), m.group(2)
        if marker[:-1].isdigit():
            marker = f"{int(marker[:-1]) + 1}."
        self.buf.insert_at_cursor(f"\n{indent}{marker} ")
        self.view.scroll_mark_onscreen(self.buf.get_insert())
        return True

    def on_click(self, view, event):
        if event.button != 1 or not event.state & Gdk.ModifierType.CONTROL_MASK:
            return False
        x, y = view.window_to_buffer_coords(Gtk.TextWindowType.TEXT, int(event.x), int(event.y))
        ok, it = view.get_iter_at_location(x, y)
        if not ok:
            return False
        start, end = it.copy(), it.copy()
        while not start.starts_line():
            start.backward_char()
            if start.get_char().isspace():
                start.forward_char()
                break
        while not end.ends_line() and not end.get_char().isspace():
            end.forward_char()
        return open_target(self.buf.get_text(start, end, False))

    def toggle_list(self, numbered):
        start, end, line = self.current_line()
        m = LIST_RE.match(line)
        body = line[m.end():] if m else line
        if m and (m.group(2)[:-1].isdigit()) == numbered:
            new = body
        else:
            new = ("1. " if numbered else "• ") + body
        self.buf.delete(start, end)
        self.buf.insert(start, new)

    # --- window -------------------------------------------------------------
    def on_grip(self, _w, event):
        if event.button == 1:
            self.begin_move_drag(1, int(event.x_root), int(event.y_root), event.time)
        elif event.button == 3:
            menu = Gtk.Menu()
            self.add_items(menu)
            menu.show_all()
            menu.popup_at_pointer(event)
        return True

    def on_corner(self, _w, event):
        self.begin_resize_drag(Gdk.WindowEdge.SOUTH_EAST, event.button,
                               int(event.x_root), int(event.y_root), event.time)
        return True

    def on_popup(self, _view, menu):
        menu.append(Gtk.SeparatorMenuItem())
        self.add_items(menu)
        menu.show_all()

    def add_items(self, menu):
        def item(label, fn):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda *_: fn())
            menu.append(mi)
        item("Bullet list on this line", lambda: self.toggle_list(False))
        item("Numbered list on this line", lambda: self.toggle_list(True))
        item("Bigger text", lambda: self.set_font(1))
        item("Smaller text", lambda: self.set_font(-1))
        menu.append(Gtk.SeparatorMenuItem())
        item("New note", self.app.new_note)
        item("Delete this note", self.delete)
        item("Hide all notes", self.app.hide_all)

    def set_font(self, step):
        self.font = max(8, min(32, self.font + step))
        self.apply_font()
        self.app.remember(self)

    def on_configure(self, _w, _event):
        GLib.idle_add(lambda: self.app.remember(self) and False)
        return False

    def delete(self):
        text = self.buf.get_text(self.buf.get_start_iter(), self.buf.get_end_iter(), False).strip()
        if text and text != "•":
            dlg = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                                    buttons=Gtk.ButtonsType.OK_CANCEL, text="Delete this note?")
            dlg.format_secondary_text("Its text will be removed for good.")
            answer = dlg.run()
            dlg.destroy()
            if answer != Gtk.ResponseType.OK:
                return
        if self.save_id:
            GLib.source_remove(self.save_id)
        try:
            os.remove(self.path)
        except OSError:
            pass
        self.app.forget(self)


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="local.aman.DesktopNote",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.notes = []
        for name, fn in (("toggle", self.toggle), ("show", self.show_all),
                         ("hide", self.hide_all), ("new", self.new_note)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda *_, fn=fn: fn())
            self.add_action(action)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()  # keep running while every note is hidden
        os.makedirs(NOTES, exist_ok=True)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.state = read_state()
        ids = sorted(f[:-4] for f in os.listdir(NOTES) if f.endswith(".txt"))
        if not ids:
            ids = [self.make_id()]
            with open(os.path.join(NOTES, f"{ids[0]}.txt"), "w") as f:
                f.write(FIRST_NOTE)
        for note_id in ids:
            self.notes.append(Note(self, note_id, self.state.get(note_id, {})))

    def do_command_line(self, cmd):
        args = cmd.get_arguments()[1:]
        arg = args[0].lstrip("-") if args else "show"
        if arg != "background":
            self.activate_action(arg if arg in ("toggle", "show", "hide", "new") else "show", None)
        return 0

    def visible(self):
        return any(n.get_visible() for n in self.notes)

    def toggle(self):
        self.hide_all() if self.visible() else self.show_all()

    def show_all(self):
        if not self.notes:
            return self.new_note()
        for note in self.notes:
            note.show()
            note.stick()
            note.present()

    def hide_all(self):
        for note in self.notes:
            note.hide()

    def make_id(self):
        return time.strftime("%Y%m%d-%H%M%S")

    def new_note(self):
        note_id = self.make_id()
        while note_id in self.state or os.path.exists(os.path.join(NOTES, f"{note_id}.txt")):
            note_id += "x"
        x, y = (self.notes[-1].get_position() if self.notes else (60, 80))
        note = Note(self, note_id, {"x": x + 40, "y": y + 40})
        note.save()
        self.notes.append(note)
        note.show()
        note.stick()
        note.present()
        note.view.grab_focus()

    def remember(self, note):
        x, y = note.get_position()
        w, h = note.get_size()
        self.state[note.id] = {"x": x, "y": y, "w": w, "h": h, "font": note.font}
        write_state(self.state)
        return True

    def forget(self, note):
        self.notes.remove(note)
        self.state.pop(note.id, None)
        write_state(self.state)
        note.destroy()


if __name__ == "__main__":
    sys.exit(App().run(sys.argv))
