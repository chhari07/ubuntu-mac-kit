import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import St from 'gi://St';
import Clutter from 'gi://Clutter';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const MAX_SCALE = 1.6;   // hovered icon
const REACH = 2.6;       // neighbours affected, in icon widths
const SMOOTH = 0.32;     // per-frame easing towards the target size
const BOUNCE_MS = 1100;  // launch bounce: two hops
const BOUNCE_HEIGHT = 0.4;

// Mac-style dock magnification for the Ubuntu dock. The dock clips its icons to
// its own area, so the grown icons are clones drawn in a layer just above it
// while the real ones are made transparent.
export class DockMagnifier {
    constructor() {
        this._docks = new Map();
        this._clones = new Map();
        this._bounces = new Map();
        this._layer = new Clutter.Actor({name: 'macbar-dock-magnifier', reactive: false});
        Main.layoutManager.uiGroup.add_child(this._layer);

        const ui = Main.layoutManager.uiGroup;
        ui.get_children().forEach(c => this._watch(c));
        this._childAddedId = ui.connect('child-added', (g, c) => this._watch(c));

        this._appStateId = Shell.AppSystem.get_default().connect('app-state-changed', (s, app) => {
            if (app.state === Shell.AppState.STARTING)
                this._bounce(app);
        });
    }

    _watch(actor) {
        if (actor.name !== 'dashtodockContainer' || this._docks.has(actor) || !actor._box)
            return;
        const ids = {
            hover: actor._box.connect('notify::hover', () => this._start()),
            destroy: actor.connect('destroy', () => {
                this._reset();
                this._docks.delete(actor);
            }),
        };
        this._docks.set(actor, ids);
    }

    // Every dash item with an icon, in order along the dock.
    _items(dock) {
        const dash = dock.dash;
        if (!dash?._box)
            return [];
        const items = [...dash._box.get_children(), dash._showAppsIcon].filter(item => {
            const bin = this._bin(item);
            return bin?.mapped && bin.width > 0;
        });
        const vertical = this._vertical(dock);
        const key = item => {
            const [x, y] = this._bin(item).get_transformed_position();
            return vertical ? y : x;
        };
        return items.sort((a, b) => key(a) - key(b));
    }

    _bin(item) {
        return item?.child?.icon?._iconBin ?? item?.icon?._iconBin ?? null;
    }

    _side(dock) {
        return dock._position ?? St.Side.BOTTOM;
    }

    _vertical(dock) {
        const side = this._side(dock);
        return side === St.Side.LEFT || side === St.Side.RIGHT;
    }

    _start() {
        if (this._timer)
            return;
        // Keep the layer right above the dock, under its labels and menus.
        const dock = [...this._docks.keys()][0];
        if (dock?.get_parent() === this._layer.get_parent())
            this._layer.get_parent().set_child_above_sibling(this._layer, dock);
        this._timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 16, () => this._frame());
    }

    _frame() {
        let busy = this._bounces.size > 0;
        const seen = new Set();
        const [px, py] = global.get_pointer();
        const now = GLib.get_monotonic_time() / 1000;

        for (const dock of this._docks.keys()) {
            const items = this._items(dock);
            if (!items.length)
                continue;
            const vertical = this._vertical(dock);
            const side = this._side(dock);
            const hovered = dock._box.hover;
            const bins = items.map(i => this._bin(i));
            const size = vertical ? bins[0].height : bins[0].width;
            const centres = bins.map(b => {
                const [x, y] = b.get_transformed_position();
                return vertical ? y + b.height / 2 : x + b.width / 2;
            });
            const pitch = centres.length > 1 ? (centres[centres.length - 1] - centres[0]) / (centres.length - 1) : size;
            const p = vertical ? py : px;

            // Target scale: a smooth bump centred on the pointer.
            const scales = items.map((item, i) => {
                const clone = this._clones.get(item);
                const current = clone?._scale ?? 1;
                let target = 1;
                if (hovered) {
                    const d = Math.min(Math.abs(p - centres[i]) / (size * REACH), 1);
                    target = 1 + (MAX_SCALE - 1) * Math.cos(d * Math.PI / 2) ** 2;
                }
                const next = current + (target - current) * SMOOTH;
                return Math.abs(next - target) < 0.004 ? target : next;
            });

            // Spread neighbours apart so grown icons don't overlap, keeping the
            // spot under the pointer still.
            const extra = scales.map(s => size * (s - 1));
            const f = (p - (centres[0] - pitch / 2)) / pitch;
            const leftExtra = extra.reduce((sum, e, j) => sum + e * Math.min(Math.max(f - j, 0), 1), 0);
            let before = 0;

            items.forEach((item, i) => {
                seen.add(item);
                const shift = before + extra[i] / 2 - leftExtra;
                before += extra[i];
                const bounce = this._bounceOffset(item, now) * size;
                const active = scales[i] !== 1 || shift !== 0 || bounce !== 0;
                busy ||= active;
                if (!active) {
                    this._drop(item);
                    return;
                }
                this._place(item, bins[i], side, vertical, scales[i], shift, bounce);
            });
        }

        // Icons that left the dock (app closed) lose their clone too.
        [...this._clones.keys()].filter(item => !seen.has(item)).forEach(item => this._drop(item));

        if (busy)
            return GLib.SOURCE_CONTINUE;
        this._timer = 0;
        this._reset();
        return GLib.SOURCE_REMOVE;
    }

    _place(item, bin, side, vertical, scale, shift, bounce) {
        let clone = this._clones.get(item);
        if (!clone) {
            clone = new Clutter.Clone({source: bin, reactive: false});
            clone._bin = bin;
            clone._binGone = false;
            bin.connectObject('destroy', () => (clone._binGone = true), clone);
            this._layer.add_child(clone);
            this._clones.set(item, clone);
            bin.opacity = 0;
        }
        clone._scale = scale;
        const [x, y] = bin.get_transformed_position();
        clone.set_size(bin.width, bin.height);
        clone.set_position(Math.round(x), Math.round(y));
        // Grow away from the screen edge the dock sits on.
        const pivot = {
            [St.Side.BOTTOM]: [0.5, 1], [St.Side.TOP]: [0.5, 0],
            [St.Side.LEFT]: [0, 0.5], [St.Side.RIGHT]: [1, 0.5],
        }[side];
        clone.set_pivot_point(...pivot);
        clone.set_scale(scale, scale);
        const out = side === St.Side.BOTTOM || side === St.Side.RIGHT ? -1 : 1;
        clone.translation_x = vertical ? out * bounce : shift;
        clone.translation_y = vertical ? shift : out * bounce;

        // Lift the app-name label clear of the grown icon.
        if (item.label) {
            const lift = out * (vertical ? bin.width : bin.height) * (scale - 1);
            item.label.translation_x = vertical ? lift : 0;
            item.label.translation_y = vertical ? 0 : lift;
        }
    }

    _drop(item) {
        const clone = this._clones.get(item);
        if (!clone)
            return;
        if (!clone._binGone)
            clone._bin.opacity = 255;
        clone.destroy();
        this._clones.delete(item);
        if (item.label)
            item.label.translation_x = item.label.translation_y = 0;
    }

    _bounce(app) {
        for (const dock of this._docks.keys()) {
            const item = this._items(dock).find(i => i.child?.app === app);
            if (item) {
                this._bounces.set(item, GLib.get_monotonic_time() / 1000);
                this._start();
            }
        }
    }

    _bounceOffset(item, now) {
        const startedAt = this._bounces.get(item);
        if (startedAt === undefined)
            return 0;
        const t = (now - startedAt) / BOUNCE_MS;
        if (t >= 1) {
            this._bounces.delete(item);
            return 0;
        }
        return BOUNCE_HEIGHT * Math.abs(Math.sin(t * 2 * Math.PI)) * (1 - t * 0.5);
    }

    _reset() {
        if (this._timer)
            GLib.source_remove(this._timer);
        this._timer = 0;
        [...this._clones.keys()].forEach(item => this._drop(item));
        this._bounces.clear();
    }

    destroy() {
        this._reset();
        Main.layoutManager.uiGroup.disconnect(this._childAddedId);
        Shell.AppSystem.get_default().disconnect(this._appStateId);
        for (const [dock, ids] of this._docks) {
            dock._box?.disconnect(ids.hover);
            dock.disconnect(ids.destroy);
        }
        this._docks.clear();
        this._layer.destroy();
    }
}
