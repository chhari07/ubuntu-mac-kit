#!/usr/bin/env python3
"""GitHub contribution calendar for the desktop, Mac-style glass card.

Reads the public calendar at github.com/users/<user>/contributions (no token),
for the user named in ~/.config/github-widget/config.json ({"user": "octocat"}),
caches it in ~/.cache/github-widget/data.json, and refreshes every hour, when the
day changes, after the laptop wakes, and when you click the refresh arrow.
Drag the card anywhere (position is remembered); the logo opens your profile, right-click for menu.

Runs as a single background app; `widget.py --toggle | --show | --hide | --refresh`
(or the org.gtk.Actions D-Bus interface) controls it. `--background` starts with the
last visibility.
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

os.environ.setdefault("GDK_BACKEND", "x11")  # Wayland apps can't place their own window

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

CONF = os.path.expanduser("~/.config/github-widget")
STATE = os.path.join(CONF, "state.json")
CONFIG = os.path.join(CONF, "config.json")
CACHE = os.path.expanduser("~/.cache/github-widget/data.json")
HOUR = 3600
LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "github-mark.svg")

WEEKS = 53

CSS = b"""
window { background-color: transparent; }
#card { background-color: rgba(22, 24, 28, 0.78); border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.18); color: rgba(255,255,255,0.95);
        font-family: Inter, Ubuntu, sans-serif; }
#title { font-size: 14px; font-weight: 600; }
.dim { color: rgba(255,255,255,0.55); font-size: 12px; }
#refresh { font-size: 15px; color: rgba(255,255,255,0.75); }
#refresh:hover { color: #ffffff; }
.month, .legend { font-size: 10px; color: rgba(255,255,255,0.55); }
.cell { min-width: 11px; min-height: 11px; border-radius: 3px; }
.leg { min-width: 10px; min-height: 10px; border-radius: 3px; }
.l0 { background-color: rgba(255,255,255,0.09); } .l1 { background-color: #0e4429; }
.l2 { background-color: #006d32; } .l3 { background-color: #26a641; } .l4 { background-color: #39d353; }
#strip { background-color: rgba(255,255,255,0.04); border-top: 1px solid rgba(255,255,255,0.12);
         border-radius: 0 0 18px 18px; }
.stat { padding: 11px 16px 12px 16px; border-left: 1px solid rgba(255,255,255,0.08); }
.stat.first { border-left: none; }
.stat-label { font-size: 11px; color: rgba(255,255,255,0.55); }
.stat-value { font-size: 22px; font-weight: 600; }
.stat-value.live { color: #39d353; }
.stat-unit { font-size: 12px; color: rgba(255,255,255,0.6); }
"""

DAY_RE = re.compile(r'data-date="([\d-]+)" id="([^"]+)" data-level="(\d)"')
TIP_RE = re.compile(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]*)')


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


USER = read_json(CONFIG).get("user", "").strip()
URL = f"https://github.com/users/{USER}/contributions"


def write_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, path)
    except OSError:
        pass


def fetch():
    """Download and parse the calendar into {date: [count, level]}."""
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 github-widget"})
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", "replace")
    ids = {cid: (date, int(level)) for date, cid, level in DAY_RE.findall(html)}
    days = {}
    for cid, text in TIP_RE.findall(html):
        if cid in ids:
            date, level = ids[cid]
            n = re.match(r"(\d[\d,]*)", text.strip())
            days[date] = [int(n.group(1).replace(",", "")) if n else 0, level]
    if not days:
        raise ValueError("no calendar found in page")
    return {"days": days, "fetched": time.time()}


def stats(days):
    keys = sorted(days)
    today = dt.date.today().isoformat()
    if today not in days:
        today = keys[-1]
    # current streak stays alive through today even before the first commit of the day
    cur, d = 0, dt.date.fromisoformat(today)
    if days[today][0] == 0:
        d -= dt.timedelta(days=1)
    while days.get(d.isoformat(), [0])[0] > 0:
        cur += 1
        d -= dt.timedelta(days=1)
    best = run = 0
    for k in keys:
        run = run + 1 if days[k][0] > 0 else 0
        best = max(best, run)
    return {"total": sum(v[0] for v in days.values()), "today": days[today][0],
            "cur": cur, "best": best}


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def box(cls=None, w=None, h=None):
    b = Gtk.Box()
    if cls:
        for c in cls.split():
            b.get_style_context().add_class(c)
    if w:
        b.set_size_request(w, h)
    return b


def label(text="", cls=None, name=None, xalign=0):
    lb = Gtk.Label(label=text, xalign=xalign)
    if cls:
        for c in cls.split():
            lb.get_style_context().add_class(c)
    if name:
        lb.set_name(name)
    return lb


def clickable(child, fn, tip=None):
    """EventBox that runs fn on left click and stops the click from starting a drag."""
    ev = Gtk.EventBox()
    ev.add(child)
    if tip:
        ev.set_tooltip_text(tip)
    ev.connect("button-press-event", lambda _w, e: (fn(), True)[1] if e.button == 1 else False)
    ev.connect("realize", lambda w: w.get_window().set_cursor(
        Gdk.Cursor.new_from_name(w.get_display(), "pointer")))
    return ev


class Widget(Gtk.Window):
    def __init__(self, app, geo):
        super().__init__(title="GitHub Widget")
        self.app = app

        visual = self.get_screen().get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.stick()

        drag = Gtk.EventBox()
        drag.set_visible_window(False)
        drag.connect("button-press-event", self.on_press)
        drag.connect("realize", lambda w: w.get_window().set_cursor(
            Gdk.Cursor.new_from_name(w.get_display(), "move")))
        self.add(drag)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.set_name("card")
        drag.add(card)

        # title bar: traffic lights, title, updated + refresh
        top = Gtk.Box(spacing=8, margin_top=14, margin_bottom=8, margin_start=18, margin_end=18)
        logo = Gtk.Image.new_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_size(LOGO, 20, 20))
        top.pack_start(clickable(logo, app.open_profile, "Open GitHub profile"), False, False, 0)
        title = label(f"GitHub · {USER}", name="title")
        title.set_margin_start(2)
        top.pack_start(title, False, False, 0)
        top.pack_end(clickable(label("↻", name="refresh"), app.refresh, "Refresh now"), False, False, 0)
        self.status = label("", "dim")
        top.pack_end(self.status, False, False, 0)
        card.pack_start(top, False, False, 0)

        # calendar: row 0 = month names, rows 1-7 = Sunday..Saturday
        self.grid = Gtk.Grid(column_spacing=2, row_spacing=2, margin_start=18, margin_end=18)
        card.pack_start(self.grid, False, False, 0)

        legend = Gtk.Box(spacing=3, margin_top=8, margin_bottom=10, margin_end=18, halign=Gtk.Align.END)
        legend.pack_start(label("Less", "legend"), False, False, 2)
        for lv in range(5):
            legend.pack_start(box(f"leg l{lv}", 10, 10), False, False, 0)
        legend.pack_start(label("More", "legend"), False, False, 2)
        card.pack_start(legend, False, False, 0)

        # stats strip
        strip = Gtk.Box(homogeneous=True)
        strip.set_name("strip")
        self.values = []
        for i, name in enumerate(("Contributions (last year)", "Current streak", "Longest streak", "Today")):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            col.get_style_context().add_class("stat")
            if i == 0:
                col.get_style_context().add_class("first")
            col.pack_start(label(name, "stat-label"), False, False, 0)
            row = Gtk.Box(spacing=5)
            value, unit = label("–", "stat-value"), label("", "stat-unit")
            unit.set_valign(Gtk.Align.END)
            unit.set_margin_bottom(4)
            row.pack_start(value, False, False, 0)
            row.pack_start(unit, False, False, 0)
            col.pack_start(row, False, False, 0)
            strip.pack_start(col, True, True, 0)
            self.values.append((value, unit))
        card.pack_start(strip, False, False, 0)

        self.connect("configure-event", lambda *_: GLib.idle_add(self.app.remember) and False)
        self.connect("delete-event", lambda *_: self.app.hide() or True)
        drag.show_all()
        self.update()

        w, h = self.get_preferred_size()[1].width, self.get_preferred_size()[1].height
        display = Gdk.Display.get_default()
        area = (display.get_primary_monitor() or display.get_monitor(0)).get_workarea()
        self.move(geo.get("x", area.x + area.width - w - 40), geo.get("y", area.y + area.height - h - 30))

    def update(self):
        data = self.app.data
        days = data.get("days", {})

        if self.app.busy:
            status = "Updating…"
        elif not days:
            status = "Offline · no data yet" if self.app.error else "No data yet"
        else:
            status = "Updated " + time.strftime("%-I:%M %p", time.localtime(data["fetched"]))
            if self.app.error:
                status = "Offline · " + status.lower()
        self.status.set_text(status)
        self.status.set_tooltip_text(self.app.error)

        for child in self.grid.get_children():
            self.grid.remove(child)
        if days:
            keys = sorted(days)[-(WEEKS * 7):]
            first = dt.date.fromisoformat(keys[0])
            offset = (first.weekday() + 1) % 7  # Sunday = row 0
            last_month = None
            for k in keys:
                d = dt.date.fromisoformat(k)
                idx = (d - first).days + offset
                col, row = idx // 7, idx % 7
                if col >= WEEKS:
                    continue
                n, lv = days[k]
                cell = box(f"cell l{lv}", 11, 11)
                count = plural(n, "contribution") if n else "No contributions"
                cell.set_tooltip_text(f"{count} on {d.strftime('%a, %-d %b %Y')}")
                self.grid.attach(cell, col, row + 1, 1, 1)
                if row == 0 and d.day <= 7 and d.month != last_month and col <= WEEKS - 3:
                    self.grid.attach(label(d.strftime("%b"), "month"), col, 0, 3, 1)
                    last_month = d.month
            self.grid.show_all()

        st = stats(days) if days else None
        rows = [(st and st["total"], ""), (st and st["cur"], "day"),
                (st and st["best"], "day"), (st and st["today"], "contribution")]
        for i, ((value, unit), (vl, ul)) in enumerate(zip(rows, self.values)):
            vl.set_text("–" if value is None else str(value))
            ul.set_text(unit if not unit or value == 1 else unit + "s")
            ctx = vl.get_style_context()
            if i == 3 and value:
                ctx.add_class("live")
            else:
                ctx.remove_class("live")

    def on_press(self, _w, event):
        if event.button == 3:
            menu = Gtk.Menu()
            for text, fn in (("Refresh now", self.app.refresh), ("Open GitHub profile", self.app.open_profile),
                             (None, None), ("Hide widget", self.app.hide)):
                menu.append(Gtk.SeparatorMenuItem() if text is None else self.item(text, fn))
            menu.show_all()
            menu.popup_at_pointer(event)
        elif event.button == 1 and event.type == Gdk.EventType.BUTTON_PRESS:
            self.begin_move_drag(1, int(event.x_root), int(event.y_root), event.time)
        return True

    @staticmethod
    def item(text, fn):
        mi = Gtk.MenuItem(label=text)
        mi.connect("activate", lambda *_: fn())
        return mi


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="io.github.chhari07.GitHubWidget",
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.win = None
        self.busy = False
        self.error = None
        self.day = dt.date.today()
        for name, fn in (("toggle", self.toggle), ("show", self.show), ("hide", self.hide),
                         ("refresh", self.refresh)):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda *_, fn=fn: fn())
            self.add_action(action)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.hold()  # keep running while hidden
        self.state = read_json(STATE)
        self.data = read_json(CACHE)
        self.win = Widget(self, self.state)
        GLib.timeout_add_seconds(60, self.tick)
        self.watch_sleep()
        self.refresh()

    def do_command_line(self, cmd):
        args = cmd.get_arguments()[1:]
        arg = args[0].lstrip("-") if args else "show"
        if arg == "background":
            if self.state.get("visible", True):
                self.show()
        else:
            self.activate_action(arg if arg in ("toggle", "show", "hide", "refresh") else "show", None)
        return 0

    # --- visibility ---------------------------------------------------------
    def toggle(self):
        self.hide() if self.win.get_visible() else self.show()

    def show(self):
        if "x" in self.state:  # the window manager may re-place a re-shown window
            self.win.move(self.state["x"], self.state["y"])
        self.win.show()
        self.win.stick()
        self.win.present()
        self.state["visible"] = True
        write_json(STATE, self.state)

    def hide(self):
        self.remember()
        self.win.hide()
        self.state["visible"] = False
        write_json(STATE, self.state)

    def remember(self):
        if self.win.get_visible():
            self.state["x"], self.state["y"] = self.win.get_position()
            write_json(STATE, self.state)
        return False

    def open_profile(self):
        env = dict(os.environ)
        env.pop("GDK_BACKEND", None)
        subprocess.Popen(["xdg-open", f"https://github.com/{USER}"], env=env, start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # --- updates ------------------------------------------------------------
    def refresh(self):
        if self.busy:
            return
        self.busy = True
        self.win.update()
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        try:
            result, err = fetch(), None
        except Exception as e:  # network down, GitHub changed, etc.
            result, err = None, str(e)
        GLib.idle_add(self._fetched, result, err)

    def _fetched(self, result, err):
        self.busy, self.error = False, err
        if result:
            self.data = result
            write_json(CACHE, result)
        self.win.update()
        return False

    def tick(self):
        """Every minute: refresh when the hour is up, the day changed, or the last try failed."""
        age = time.time() - self.data.get("fetched", 0)
        new_day = dt.date.today() != self.day
        self.day = dt.date.today()
        if new_day or age >= HOUR or (self.error and age >= 300):
            self.refresh()
        return True

    def watch_sleep(self):
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            bus.signal_subscribe("org.freedesktop.login1", "org.freedesktop.login1.Manager",
                                 "PrepareForSleep", "/org/freedesktop/login1", None,
                                 Gio.DBusSignalFlags.NONE, self.on_sleep)
        except GLib.Error:
            pass

    def on_sleep(self, _conn, _sender, _path, _iface, _signal, params):
        if not params.unpack()[0]:  # False = just woke up; give Wi-Fi a moment
            GLib.timeout_add_seconds(15, lambda: self.refresh() and False)


if __name__ == "__main__":
    if not USER:
        sys.exit(f'No GitHub user set. Write {{"user": "<name>"}} to {CONFIG}')
    sys.exit(App().run(sys.argv))
