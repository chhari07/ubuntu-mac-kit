import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GdkPixbuf from 'gi://GdkPixbuf';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Graphene from 'gi://Graphene';
import Meta from 'gi://Meta';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const HOME = GLib.get_home_dir();
const DESKTOP = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP) ?? `${HOME}/Desktop`;
const CACHE = GLib.build_filenamev([GLib.get_user_cache_dir(), 'desktop-stack']);
const CONFIG = GLib.build_filenamev([GLib.get_user_config_dir(), 'desktop-stack.json']);

const IMAGE_EXT = ['png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'tif', 'tiff', 'heic', 'avif'];
const MAX_ITEMS = 24;
const THUMB_PX = 320;

// Each pile: a folder, what to show from it, and where it sits by default
// (fractions of the primary monitor). Piled files are hidden from the icon grid.
const PILES = [
    {name: 'Photos & PDFs', dir: DESKTOP, exts: [...IMAGE_EXT, 'pdf'], x: 0.70, y: 0.40},
];

function ext(name) {
    const i = name.lastIndexOf('.');
    return i < 0 ? '' : name.slice(i + 1).toLowerCase();
}

// Small deterministic PRNG so a pile keeps its look between reloads.
function rng(seed) {
    let s = 0;
    for (const c of seed)
        s = (s * 31 + c.charCodeAt(0)) | 0;
    return () => {
        s = (s * 1103515245 + 12345) | 0;
        return ((s >>> 8) & 0xffff) / 0xffff;
    };
}

function loadConfig() {
    try {
        const [, bytes] = GLib.file_get_contents(CONFIG);
        return JSON.parse(new TextDecoder().decode(bytes));
    } catch (e) {
        return {};
    }
}

// Hide piled files from the desktop icon grid via the folder's .hidden list,
// leaving any entries we did not add untouched.
function setHidden(dir, cfg, names) {
    const path = GLib.build_filenamev([dir, '.hidden']);
    let lines = [];
    try {
        lines = new TextDecoder().decode(GLib.file_get_contents(path)[1]).split('\n').filter(l => l);
    } catch (e) {}
    const ours = new Set(cfg.hidden?.[dir] ?? []);
    const next = [...lines.filter(l => !ours.has(l)), ...names];
    cfg.hidden = {...cfg.hidden, [dir]: names};
    saveConfig(cfg);
    if (next.join('\n') === lines.join('\n'))
        return;
    try {
        if (next.length)
            GLib.file_set_contents(path, `${next.join('\n')}\n`);
        else
            Gio.File.new_for_path(path).delete(null);
    } catch (e) {
        logError(e, 'desktop-stack');
    }
}

function saveConfig(cfg) {
    try {
        GLib.file_set_contents(CONFIG, JSON.stringify(cfg));
    } catch (e) {
        logError(e, 'desktop-stack');
    }
}

// Returns the path of a cached PNG preview for `file`, creating it if needed.
async function thumbnail(file, info) {
    const mtime = info.get_modification_date_time()?.to_unix() ?? 0;
    const key = GLib.compute_checksum_for_string(GLib.ChecksumType.MD5, `${file.get_path()}:${mtime}`, -1);
    const out = GLib.build_filenamev([CACHE, `${key}.png`]);
    if (GLib.file_test(out, GLib.FileTest.EXISTS))
        return out;

    if (ext(file.get_basename()) === 'pdf') {
        const base = out.slice(0, -4);
        const proc = Gio.Subprocess.new(
            ['pdftoppm', '-png', '-singlefile', '-f', '1', '-l', '1', '-scale-to', `${THUMB_PX}`, file.get_path(), base],
            Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_SILENCE);
        await new Promise(resolve => proc.wait_async(null, () => resolve()));
        return proc.get_successful() ? out : null;
    }

    const stream = await new Promise((resolve, reject) => file.read_async(GLib.PRIORITY_LOW, null, (f, res) => {
        try {
            resolve(f.read_finish(res));
        } catch (e) {
            reject(e);
        }
    }));
    const pixbuf = await new Promise((resolve, reject) => GdkPixbuf.Pixbuf.new_from_stream_at_scale_async(
        stream, THUMB_PX, THUMB_PX, true, null, (s, res) => {
            try {
                resolve(GdkPixbuf.Pixbuf.new_from_stream_finish(res));
            } catch (e) {
                reject(e);
            }
        }));
    stream.close(null);
    (pixbuf.apply_embedded_orientation() ?? pixbuf).savev(out, 'png', [], []);
    return out;
}

// Opens a file in its default app and closes that app's window again as soon as
// focus moves to some other window (a click outside it, e.g. on the desktop).
class Viewer {
    constructor() {
        this._window = null;
        this._waitUntil = 0;
        this._focusId = global.display.connect('notify::focus-window', () => this._onFocus());
    }

    open(file) {
        // The first new normal window to take focus within 10 s is the viewer.
        this._known = new Set(global.display.list_all_windows());
        this._waitUntil = GLib.get_monotonic_time() + 10 * GLib.USEC_PER_SEC;
        Gio.AppInfo.launch_default_for_uri(file.get_uri(), global.create_app_launch_context(0, -1));
    }

    _onFocus() {
        const w = global.display.focus_window;
        if (!w)
            return;
        if (this._window && w !== this._window && !this._belongs(w)) {
            const old = this._window;
            this._untrack();
            old.delete(global.get_current_time());
        }
        if (this._waitUntil && GLib.get_monotonic_time() < this._waitUntil &&
            !this._known.has(w) && w.get_window_type() === Meta.WindowType.NORMAL) {
            this._waitUntil = 0;
            this._window = w;
            this._unmanagedId = w.connect('unmanaged', () => this._untrack());
        }
    }

    // Dialogs of the viewer (print, save as...) don't count as clicking outside.
    _belongs(w) {
        for (let t = w.get_transient_for(); t; t = t.get_transient_for()) {
            if (t === this._window)
                return true;
        }
        return false;
    }

    _untrack() {
        this._window?.disconnect(this._unmanagedId);
        this._window = null;
    }

    destroy() {
        this._untrack();
        global.display.disconnect(this._focusId);
    }
}

class Pile {
    constructor(def, layer, cfg, viewer) {
        this._def = def;
        this._viewer = viewer;
        this._cfg = cfg;
        this._dir = Gio.File.new_for_path(def.dir);
        this._gen = 0;

        this.actor = new Clutter.Actor();
        layer.add_child(this.actor);

        this._label = new St.Label({style_class: 'dstack-label', reactive: true, text: def.name});
        this._label.connect('button-press-event', (a, e) => {
            if (e.get_button() === 3) {
                this._tidy();
                return Clutter.EVENT_STOP;
            }
            return this._press(e, null, null);
        });

        try {
            this._monitor = this._dir.monitor_directory(Gio.FileMonitorFlags.NONE, null);
            this._monitor.connect('changed', (m, f) => {
                if (f.get_basename() !== '.hidden')
                    this._queueRebuild();
            });
        } catch (e) {
            this._monitor = null;
        }
        this.rebuild();
    }

    _queueRebuild() {
        if (this._timeout)
            return;
        this._timeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 800, () => {
            this._timeout = 0;
            this.rebuild();
            return GLib.SOURCE_REMOVE;
        });
    }

    _files() {
        const out = [];
        try {
            const en = this._dir.enumerate_children('standard::name,standard::is-hidden,time::modified',
                Gio.FileQueryInfoFlags.NONE, null);
            let info;
            while ((info = en.next_file(null))) {
                if (!info.get_name().startsWith('.') && this._def.exts.includes(ext(info.get_name())))
                    out.push([this._dir.get_child(info.get_name()), info]);
            }
        } catch (e) {
            return [];
        }
        out.sort((a, b) => (b[1].get_modification_date_time()?.to_unix() ?? 0) -
            (a[1].get_modification_date_time()?.to_unix() ?? 0));
        return out.slice(0, MAX_ITEMS);
    }

    async rebuild() {
        const gen = ++this._gen;
        const items = [];
        for (const [file, info] of this._files()) {
            try {
                const thumb = await thumbnail(file, info);
                if (thumb)
                    items.push([file, thumb]);
            } catch (e) {
                logError(e, `desktop-stack: ${file.get_path()}`);
            }
            if (gen !== this._gen || !this.actor)
                return;
        }
        setHidden(this._def.dir, this._cfg, items.map(([f]) => f.get_basename()));
        this._render(items);
    }

    _render(items) {
        this._items = items;
        if (this._label.get_parent())
            this.actor.remove_child(this._label);
        this.actor.destroy_all_children();
        if (!items.length)
            return;

        const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        const rand = rng(this._def.name);
        const spacing = 50 * scale;

        // Golden-angle spiral with jitter: dense in the middle, ragged at the edges.
        // Oldest go in first so the newest end up on top near the centre.
        const saved = this._cfg.tiles?.[this._def.name] ?? {};
        const tiles = [];
        items.slice().reverse().forEach(([file, thumb], idx) => {
            const i = items.length - 1 - idx;
            const size = (82 + rand() * 38) * scale;
            let w = size, h = size;
            try {
                const [, tw, th] = GdkPixbuf.Pixbuf.get_file_info(thumb);
                if (tw && th) {
                    const r = Math.min(1.45, Math.max(0.7, th / tw));
                    if (r > 1)
                        w = size / r;
                    else
                        h = size * r;
                }
            } catch (e) {}

            const a = i * 2.39996 + rand() * 0.4;
            const rad = spacing * Math.sqrt(i) * (0.9 + rand() * 0.3);
            const pos = saved[file.get_basename()];
            const tile = new St.Widget({
                style_class: 'dstack-tile',
                style: `background-image: url("${Gio.File.new_for_path(thumb).get_uri()}");`,
                reactive: true,
                track_hover: true,
                width: w,
                height: h,
                x: Math.round(pos ? pos.x * scale : rad * Math.cos(a) - w / 2),
                y: Math.round(pos ? pos.y * scale : rad * Math.sin(a) * 0.85 - h / 2),
                pivot_point: new Graphene.Point({x: 0.5, y: 0.5}),
            });
            tile.connect('notify::hover', () => {
                if (tile.hover)
                    this.actor.set_child_above_sibling(tile, null);
                tile.ease({
                    scale_x: tile.hover ? 1.14 : 1,
                    scale_y: tile.hover ? 1.14 : 1,
                    duration: 140,
                    mode: Clutter.AnimationMode.EASE_OUT_QUAD,
                });
            });
            tile.connect('button-press-event', (t, e) => this._press(e, file, tile));
            tiles.push([tile, pos?.z ?? 0]);
        });
        // Tiles the user dragged stay on top, most recently dragged highest.
        tiles.sort((p, q) => p[1] - q[1]).forEach(([t]) => this.actor.add_child(t));
        this._placeLabel();
        this._place();
    }

    _placeLabel() {
        const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        const tiles = this.actor.get_children().filter(c => c !== this._label);
        if (this._label.get_parent())
            this.actor.remove_child(this._label);
        if (!tiles.length)
            return;

        // Centre the label under the pile.
        const bottom = Math.max(...tiles.map(t => t.y + t.height));
        const left = Math.min(...tiles.map(t => t.x));
        const right = Math.max(...tiles.map(t => t.x + t.width));
        this._label.text = `${this._def.name}  ·  ${tiles.length}`;
        this.actor.add_child(this._label);
        const [, lw] = this._label.get_preferred_width(-1);
        this._label.set_position(Math.round((left + right - lw) / 2), Math.round(bottom + 8 * scale));
    }

    // Right-click on the label: put every tile back into the pile.
    _tidy() {
        if (!this._cfg.tiles?.[this._def.name])
            return;
        delete this._cfg.tiles[this._def.name];
        saveConfig(this._cfg);
        this._render(this._items ?? []);
    }

    _place() {
        const mon = Main.layoutManager.primaryMonitor;
        if (!mon)
            return;
        const pos = this._cfg[this._def.name] ?? {x: this._def.x, y: this._def.y};
        this.actor.set_position(Math.round(mon.x + pos.x * mon.width), Math.round(mon.y + pos.y * mon.height));
    }

    // While files are dragged in from another app, let the drop fall through to the
    // desktop icons window underneath (it moves them into ~/Desktop, so they join the pile).
    setDropMode(on) {
        for (const child of this.actor?.get_children() ?? []) {
            child.reactive = !on;
            if (!on)
                child.remove_style_class_name('dstack-drop');
        }
    }

    // Glow while a dragged file is over the pile.
    dragOver(x, y) {
        const children = this.actor?.get_children() ?? [];
        if (!children.length)
            return;
        const pad = 30 * St.ThemeContext.get_for_stage(global.stage).scale_factor;
        const over = children.some(c => {
            const r = c.get_transformed_extents();
            return x >= r.get_x() - pad && x <= r.get_x() + r.get_width() + pad &&
                y >= r.get_y() - pad && y <= r.get_y() + r.get_height() + pad;
        });
        children.forEach(c => (over ? c.add_style_class_name : c.remove_style_class_name).call(c, 'dstack-drop'));
    }

    // Double-click opens the file (closed again on a click outside it); clicking the
    // label opens the Desktop folder. Dragging a tile moves just that tile;
    // dragging the label moves the whole pile.
    _press(event, file, tile) {
        if (event.get_button() !== 1)
            return Clutter.EVENT_PROPAGATE;
        // Clutter 14 has no click count, so spot the double-click ourselves.
        const time = event.get_time();
        const path = file?.get_path();
        const double = path && this._lastClick?.path === path &&
            time - this._lastClick.time <= Clutter.Settings.get_default().double_click_time;
        this._lastClick = double ? null : {path, time};
        const target = tile ?? this.actor;
        const [sx, sy] = event.get_coords();
        const [ax, ay] = [target.x, target.y];
        let dragging = false;

        this._grabId = global.stage.connect('captured-event', (stage, ev) => {
            const type = ev.type();
            if (type === Clutter.EventType.MOTION) {
                const [x, y] = ev.get_coords();
                if (!dragging && Math.hypot(x - sx, y - sy) > 6) {
                    dragging = true;
                    if (tile) {
                        this.actor.set_child_above_sibling(tile, null);
                        tile.ease({opacity: 230, duration: 100, mode: Clutter.AnimationMode.EASE_OUT_QUAD});
                    }
                }
                if (dragging)
                    target.set_position(Math.round(ax + x - sx), Math.round(ay + y - sy));
                return Clutter.EVENT_STOP;
            }
            if (type === Clutter.EventType.BUTTON_RELEASE) {
                global.stage.disconnect(this._grabId);
                this._grabId = 0;
                if (dragging && tile) {
                    const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
                    const all = {...this._cfg.tiles?.[this._def.name]};
                    const z = Math.max(0, ...Object.values(all).map(p => p.z ?? 0)) + 1;
                    all[file.get_basename()] = {x: tile.x / scale, y: tile.y / scale, z};
                    this._cfg.tiles = {...this._cfg.tiles, [this._def.name]: all};
                    saveConfig(this._cfg);
                    tile.ease({opacity: 255, duration: 100, mode: Clutter.AnimationMode.EASE_OUT_QUAD});
                    this._placeLabel();
                } else if (dragging) {
                    const mon = Main.layoutManager.primaryMonitor;
                    this._cfg[this._def.name] = {
                        x: (this.actor.x - mon.x) / mon.width,
                        y: (this.actor.y - mon.y) / mon.height,
                    };
                    saveConfig(this._cfg);
                } else if (!file) {
                    Gio.AppInfo.launch_default_for_uri(this._dir.get_uri(),
                        global.create_app_launch_context(0, -1));
                } else if (double) {
                    this._viewer.open(file);
                }
                return Clutter.EVENT_STOP;
            }
            return Clutter.EVENT_PROPAGATE;
        });
        return Clutter.EVENT_STOP;
    }

    destroy() {
        this._gen++;
        if (this._timeout)
            GLib.source_remove(this._timeout);
        if (this._grabId)
            global.stage.disconnect(this._grabId);
        this._monitor?.cancel();
        setHidden(this._def.dir, this._cfg, []);
        this._label.destroy();
        this.actor.destroy();
        this.actor = null;
    }
}

export default class DesktopStack extends Extension {
    enable() {
        GLib.mkdir_with_parents(CACHE, 0o755);
        this._layer = new Clutter.Actor({name: 'desktop-stack'});
        global.window_group.add_child(this._layer);

        const cfg = loadConfig();
        this._viewer = new Viewer();
        this._piles = PILES.map(def => new Pile(def, this._layer, cfg, this._viewer));

        const dnd = global.backend.get_dnd();
        this._dndIds = [
            dnd.connect('dnd-enter', () => this._piles.forEach(p => p.setDropMode(true))),
            dnd.connect('dnd-position-change', (d, x, y) => this._piles.forEach(p => p.dragOver(x, y))),
            dnd.connect('dnd-leave', () => this._piles.forEach(p => p.setDropMode(false))),
        ];

        this._restackId = global.display.connect('restacked', () => this._restack());
        this._monitorsId = Main.layoutManager.connect('monitors-changed', () => this._piles.forEach(p => p._place()));
        this._restack();
    }

    // Sit right above the desktop-icons window (or the wallpaper) and below every app window.
    _restack() {
        let anchor = Main.layoutManager._backgroundGroup;
        for (const actor of global.get_window_actors()) {
            const w = actor.meta_window;
            if (w.get_gtk_application_id() === 'com.rastersoft.ding' ||
                (w.get_title() ?? '').startsWith('Desktop Icons'))
                anchor = actor;
        }
        if (anchor?.get_parent() === global.window_group)
            global.window_group.set_child_above_sibling(this._layer, anchor);
        else
            global.window_group.set_child_below_sibling(this._layer, null);
    }

    disable() {
        global.display.disconnect(this._restackId);
        Main.layoutManager.disconnect(this._monitorsId);
        const dnd = global.backend.get_dnd();
        this._dndIds.forEach(id => dnd.disconnect(id));
        this._dndIds = null;
        this._piles.forEach(p => p.destroy());
        this._piles = null;
        this._viewer.destroy();
        this._viewer = null;
        this._layer.destroy();
        this._layer = null;
    }
}
