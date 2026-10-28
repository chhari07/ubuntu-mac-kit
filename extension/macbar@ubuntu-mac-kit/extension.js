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

import {DockMagnifier} from './dock.js';

const NOTES_BUS = 'io.github.chhari07.DesktopNote';
const NOTES_PATH = '/io/github/chhari07/DesktopNote';
const NOTES_SCRIPT = GLib.build_filenamev([GLib.get_home_dir(), '.local/share/desktop-note/note.py']);
const GITHUB_BUS = 'io.github.chhari07.GitHubWidget';
const GITHUB_PATH = '/io/github/chhari07/GitHubWidget';
const GITHUB_SCRIPT = GLib.build_filenamev([GLib.get_home_dir(), '.local/share/github-widget/widget.py']);

function run(argv) {
    try {
        Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
    } catch (e) {
        logError(e, 'macbar');
    }
}

// Ask a running helper app to do something; start it if it is not running.
function appAction(bus, path, script, name) {
    Gio.DBus.session.call(bus, path, 'org.gtk.Actions', 'Activate',
        new GLib.Variant('(sava{sv})', [name, [], {}]), null,
        Gio.DBusCallFlags.NO_AUTO_START, 1000, null, (conn, res) => {
            try {
                conn.call_finish(res);
            } catch (e) {
                run(['env', 'GDK_BACKEND=x11', 'python3', script, `--${name === 'toggle' ? 'show' : name}`]);
            }
        });
}

const notesAction = name => appAction(NOTES_BUS, NOTES_PATH, NOTES_SCRIPT, name);
const githubAction = name => appAction(GITHUB_BUS, GITHUB_PATH, GITHUB_SCRIPT, name);

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

// Top-bar button for a helper app: left click toggles it, right click opens a menu.
const ToggleButton = GObject.registerClass(
class ToggleButton extends PanelMenu.Button {
    _init(name, icon, action, items) {
        super._init(0.5, name);
        this._action = action;
        this.add_child(new St.Icon({
            gicon: Gio.icon_new_for_string(icon),
            style_class: 'system-status-icon macbar-sticky',
        }));
        for (const [label, fn] of items)
            this.menu.addAction(label, fn);

        // GNOME 50+ opens the menu from a click gesture, which ignores vfunc_event,
        // so keep that gesture for right click and add one for left click.
        if (this._clickGesture) {
            this._clickGesture.set_required_button(Clutter.BUTTON_SECONDARY);
            const toggle = new Clutter.ClickGesture();
            toggle.set_required_button(Clutter.BUTTON_PRIMARY);
            toggle.connect('recognize', () => this._action('toggle'));
            this.add_action(toggle);
        }
    }

    // Left click toggles the app straight away; right click opens the menu.
    // GNOME 46 to 49 only, see the gestures above for newer versions.
    vfunc_event(event) {
        if (!this._clickGesture &&
            event.type() === Clutter.EventType.BUTTON_PRESS && event.get_button() === 1) {
            this._action('toggle');
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

        this._sticky = new ToggleButton('Sticky Notes', `${this.path}/icons/sticky-note.svg`, notesAction, [
            ['Show / Hide All Notes', () => notesAction('toggle')],
            ['New Note', () => notesAction('new')],
        ]);
        panel.addToStatusArea('macbar-sticky', this._sticky, 0, 'right');

        // The GitHub widget is optional, so only show its button when it is installed.
        if (GLib.file_test(GITHUB_SCRIPT, GLib.FileTest.EXISTS)) {
            this._github = new ToggleButton('GitHub Widget', `${this.path}/icons/github-mark.svg`, githubAction, [
                ['Show / Hide GitHub Widget', () => githubAction('toggle')],
                ['Refresh Now', () => githubAction('refresh')],
            ]);
            panel.addToStatusArea('macbar-github', this._github, 0, 'right');
        }

        // Clock on the right, like macOS
        const clock = panel.statusArea.dateMenu.container;
        this._clockParent = clock.get_parent();
        this._clockParent.remove_child(clock);
        panel._rightBox.add_child(clock);

        // Mac-style magnify and launch bounce on the Ubuntu dock
        try {
            this._dock = new DockMagnifier();
        } catch (e) {
            logError(e, 'macbar: dock magnifier');
        }
    }

    disable() {
        this._dock?.destroy();
        this._dock = null;

        const panel = Main.panel;
        const clock = panel.statusArea.dateMenu.container;
        clock.get_parent()?.remove_child(clock);
        panel._centerBox.insert_child_at_index(clock, 0);

        this._logo?.destroy();
        this._sticky?.destroy();
        this._github?.destroy();
        this._logo = this._sticky = this._github = null;

        this._activities?.show();
        this._activities = null;

        if (this._blur)
            panel.remove_effect_by_name('macbar-blur');
        this._blur = null;
        panel.remove_style_class_name('macbar-panel');
    }
}
