import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as SystemActions from 'resource:///org/gnome/shell/misc/systemActions.js';

const NOTES_BUS = 'local.aman.DesktopNote';
const NOTES_PATH = '/local/aman/DesktopNote';
const NOTES_SCRIPT = GLib.build_filenamev([GLib.get_home_dir(), '.local/share/desktop-note/note.py']);

function run(argv) {
    try {
        Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
    } catch (e) {
        logError(e, 'macbar');
    }
}

// Ask the running notes app to do something; start it if it is not running.
function notesAction(name) {
    Gio.DBus.session.call(NOTES_BUS, NOTES_PATH, 'org.gtk.Actions', 'Activate',
        new GLib.Variant('(sava{sv})', [name, [], {}]), null,
        Gio.DBusCallFlags.NO_AUTO_START, 1000, null, (conn, res) => {
            try {
                conn.call_finish(res);
            } catch (e) {
                run(['env', 'GDK_BACKEND=x11', 'python3', NOTES_SCRIPT, `--${name === 'toggle' ? 'show' : name}`]);
            }
        });
}

const LogoMenu = GObject.registerClass(
class LogoMenu extends PanelMenu.Button {
    _init(dir) {
        super._init(0.0, 'Ubuntu Menu');
        this.add_child(new St.Icon({
            gicon: Gio.icon_new_for_string(`${dir}/icons/ubuntu-logo.svg`),
            style_class: 'macbar-logo',
        }));

        const sys = SystemActions.getDefault();
        const add = (label, fn) => this.menu.addAction(label, fn);
        const sep = () => this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        add('About This Computer', () => run(['gnome-control-center', 'system']));
        sep();
        add('System Settings…', () => run(['gnome-control-center']));
        add('App Center…', () => run(['snap-store']));
        add('All Apps', () => Main.overview.showApps());
        add('Activities', () => Main.overview.toggle());
        sep();
        add('Sleep', () => sys.activateSuspend());
        add('Restart…', () => sys.activateRestart());
        add('Shut Down…', () => sys.activatePowerOff());
        sep();
        add('Lock Screen', () => sys.activateLockScreen());
        add('Log Out…', () => sys.activateLogout());
    }
});

const StickyButton = GObject.registerClass(
class StickyButton extends PanelMenu.Button {
    _init(dir) {
        super._init(0.5, 'Sticky Notes');
        this.add_child(new St.Icon({
            gicon: Gio.icon_new_for_string(`${dir}/icons/sticky-note.svg`),
            style_class: 'system-status-icon macbar-sticky',
        }));
        this.menu.addAction('Show / Hide All Notes', () => notesAction('toggle'));
        this.menu.addAction('New Note', () => notesAction('new'));
    }

    // Left click toggles the notes straight away; right click opens the menu.
    vfunc_event(event) {
        if (event.type() === Clutter.EventType.BUTTON_PRESS && event.get_button() === 1) {
            notesAction('toggle');
            return Clutter.EVENT_STOP;
        }
        return super.vfunc_event(event);
    }
});

export default class MacBar extends Extension {
    enable() {
        const panel = Main.panel;
        panel.add_style_class_name('macbar-panel');

        try {
            this._blur = new Shell.BlurEffect({mode: Shell.BlurMode.BACKGROUND, brightness: 0.75, radius: 40});
            panel.add_effect_with_name('macbar-blur', this._blur);
        } catch (e) {
            logError(e, 'macbar: blur unavailable');
        }

        this._activities = panel.statusArea.activities;
        this._activities?.hide();

        this._logo = new LogoMenu(this.path);
        panel.addToStatusArea('macbar-logo', this._logo, 0, 'left');

        this._sticky = new StickyButton(this.path);
        panel.addToStatusArea('macbar-sticky', this._sticky, 0, 'right');

        // Clock on the right, like macOS
        const clock = panel.statusArea.dateMenu.container;
        this._clockParent = clock.get_parent();
        this._clockParent.remove_child(clock);
        panel._rightBox.add_child(clock);
    }

    disable() {
        const panel = Main.panel;
        const clock = panel.statusArea.dateMenu.container;
        clock.get_parent()?.remove_child(clock);
        panel._centerBox.insert_child_at_index(clock, 0);

        this._logo?.destroy();
        this._sticky?.destroy();
        this._logo = this._sticky = null;

        this._activities?.show();
        this._activities = null;

        if (this._blur)
            panel.remove_effect_by_name('macbar-blur');
        this._blur = null;
        panel.remove_style_class_name('macbar-panel');
    }
}
