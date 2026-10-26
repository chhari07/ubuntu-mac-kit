#!/usr/bin/env bash
# Ubuntu Mac Kit installer.
# Installs the theme files into your home folder and applies the GNOME settings.
# Nothing is written outside $HOME and sudo is never needed. Run ./uninstall.sh to undo.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD="$KIT_DIR/payload"
# shellcheck source=lib/common.sh
source "$KIT_DIR/lib/common.sh"

WITH_ICON_LOCK=1
WITH_EXTENSION=1
WITH_NOTES=1
FORCE_EXTENSION=0
WALLPAPER=""

usage() {
  cat <<EOF
$KIT_NAME $KIT_VERSION installer

Usage: ./install.sh [options]

Options:
  -y, --yes            Do not ask for confirmation
  -n, --dry-run        Show what would be done without changing anything
      --wallpaper FILE Also set FILE as the desktop wallpaper
      --no-extension   Skip the Mac Bar top-bar extension
      --no-notes       Skip the Sticky Notes app used by the top-bar note button
      --no-icon-lock   Skip the service that keeps the icon theme selected
      --force-extension
                       Enable Mac Bar on GNOME Shell versions other than 46 to 48
  -h, --help           Show this help

Undo everything with ./uninstall.sh
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes) ASSUME_YES=1 ;;
    -n|--dry-run) DRY_RUN=1 ;;
    --wallpaper) [[ $# -ge 2 ]] || die "--wallpaper needs a file"; WALLPAPER="$2"; shift ;;
    --no-extension) WITH_EXTENSION=0 ;;
    --no-notes) WITH_NOTES=0 ;;
    --no-icon-lock) WITH_ICON_LOCK=0 ;;
    --force-extension) FORCE_EXTENSION=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "Unknown option: $1" ;;
  esac
  shift
done

# ---------------------------------------------------------------------------
# Helpers that track every change so uninstall.sh can reverse it

record() {
  (( DRY_RUN )) || printf '%s\n' "$1" >> "$MANIFEST"
}

# Remember what is at $1 before the kit touches it. Files are copied, so they can be edited in place.
prepare() {
  local dst="$1" mode="${2:-move}"
  manifest_has "$dst" && return 0
  if [[ -e "$dst" || -L "$dst" ]]; then
    run mkdir -p "$(dirname "$BACKUP/files$dst")"
    if [[ "$mode" == copy ]]; then
      run cp -a "$dst" "$BACKUP/files$dst"
    else
      run mv "$dst" "$BACKUP/files$dst"
    fi
    record "replaced $dst"
  else
    record "created $dst"
  fi
}

# Copy $1 to $2, replacing whatever is there.
place() {
  local src="$1" dst="$2"
  if manifest_has "$dst"; then
    run rm -rf "$dst"
  else
    prepare "$dst" move
  fi
  run mkdir -p "$(dirname "$dst")"
  run cp -a "$src" "$dst"
}

# Write stdin to $1, replacing whatever is there.
write_file() {
  local dst="$1"
  prepare "$dst" copy
  if (( DRY_RUN )); then
    printf '  %s[dry-run]%s write %s\n' "$DIM" "$RESET" "$dst"
    cat >/dev/null
    return
  fi
  mkdir -p "$(dirname "$dst")"
  cat > "$dst"
}

# Set key=value in the [Settings] group of a GTK settings.ini file.
set_ini() {
  local file="$1" key="$2" value="$3"
  prepare "$file" copy
  if (( DRY_RUN )); then
    printf '  %s[dry-run]%s set %s=%s in %s\n' "$DIM" "$RESET" "$key" "$value" "$file"
    return
  fi
  mkdir -p "$(dirname "$file")"
  if [[ ! -f "$file" ]]; then
    printf '[Settings]\n%s=%s\n' "$key" "$value" > "$file"
  elif grep -q "^$key=" "$file"; then
    sed -i "s|^$key=.*|$key=$value|" "$file"
  elif grep -q '^\[Settings\]' "$file"; then
    sed -i "/^\[Settings\]/a $key=$value" "$file"
  else
    printf '\n[Settings]\n%s=%s\n' "$key" "$value" >> "$file"
  fi
}

# Save the current value of a GNOME setting once, then change it.
apply_setting() {
  local schema="$1" key="$2" value="$3"
  if ! has_key "$schema" "$key"; then
    skip "$schema $key is not available on this system"
    return 0
  fi
  if ! (( DRY_RUN )) && ! awk -v s="$schema" -v k="$key" '$1==s && $2==k {f=1} END {exit !f}' "$SETTINGS_BACKUP" 2>/dev/null; then
    printf '%s %s %s\n' "$schema" "$key" "$(gsettings get "$schema" "$key")" >> "$SETTINGS_BACKUP"
  fi
  run gsettings set "$schema" "$key" "$value"
}

# ---------------------------------------------------------------------------
# Pre-flight checks

require_user

[[ -d "$PAYLOAD/icons/WhiteSur-dark" && -f "$PAYLOAD/gtk-4.0/gtk.css" ]] || die "Theme files were not found in $PAYLOAD.
        This folder looks like a source checkout. Download the ready-to-install
        bundle (ubuntu-mac-kit.tar.gz) from $RELEASES_URL"

if [[ "${XDG_CURRENT_DESKTOP:-}" != *GNOME* ]]; then
  warn "This does not look like a GNOME session (XDG_CURRENT_DESKTOP=${XDG_CURRENT_DESKTOP:-unset}). Settings may have no effect."
fi

SHELL_MAJOR="$(gnome-shell --version 2>/dev/null | grep -oE '[0-9]+' | head -n1 || true)"
if (( WITH_EXTENSION )) && [[ ! "$SHELL_MAJOR" =~ ^4[678]$ ]] && ! (( FORCE_EXTENSION )); then
  warn "Mac Bar supports GNOME Shell 46 to 48, found ${SHELL_MAJOR:-none}. It will be skipped (use --force-extension to try anyway)."
  WITH_EXTENSION=0
fi

if [[ -n "$WALLPAPER" && ! -f "$WALLPAPER" ]]; then
  die "Wallpaper file not found: $WALLPAPER"
fi

printf '%s%s %s%s\n\n' "$BOLD" "$KIT_NAME" "$KIT_VERSION" "$RESET"
echo "This will install into $HOME:"
echo "  - WhiteSur-dark icons with macOS folders and file icons, macOS cursor"
echo "  - MacTahoe styling for GTK4 apps, dark mode, window buttons on the left"
echo "  - Glass dock settings (bottom, 48 px icons)"
(( WITH_EXTENSION )) && echo "  - Mac Bar top-bar extension"
(( WITH_NOTES )) && echo "  - Sticky Notes app"
(( WITH_ICON_LOCK )) && echo "  - Icon-lock service (keeps the icon theme selected)"
[[ -n "$WALLPAPER" ]] && echo "  - Wallpaper: $WALLPAPER"
echo
echo "Your current settings are backed up first. Undo with ./uninstall.sh"
(( DRY_RUN )) && echo "Dry run: nothing will be changed."
echo
confirm "Continue?" || { echo "Cancelled."; exit 1; }

(( DRY_RUN )) || mkdir -p "$STATE" "$BACKUP"
(( DRY_RUN )) || echo "$KIT_VERSION" > "$STATE/version"

# ---------------------------------------------------------------------------
section "Icons and cursor"

for theme in WhiteSur WhiteSur-dark macOS; do
  place "$PAYLOAD/icons/$theme" "$DATA/icons/$theme"
done
if command -v gtk-update-icon-cache >/dev/null; then
  for theme in WhiteSur WhiteSur-dark; do
    run gtk-update-icon-cache -q -f -t "$DATA/icons/$theme" || warn "Could not update the icon cache for $theme"
  done
fi
ok "WhiteSur-dark icons with macOS folders and file icons"
ok "macOS cursor"

# ---------------------------------------------------------------------------
section "GTK styling"

for item in gtk.css gtk-dark.css assets windows-assets; do
  if [[ -e "$PAYLOAD/gtk-4.0/$item" ]]; then
    place "$PAYLOAD/gtk-4.0/$item" "$CONF/gtk-4.0/$item"
  fi
done
ok "MacTahoe styling for GTK4 / libadwaita apps"
set_ini "$CONF/gtk-3.0/settings.ini" gtk-icon-theme-name WhiteSur-dark
set_ini "$CONF/gtk-4.0/settings.ini" gtk-icon-theme-name WhiteSur-dark
ok "GTK 3 and 4 icon theme set"

# ---------------------------------------------------------------------------
section "Desktop settings"

while read -r schema key value; do
  [[ -z "$schema" || "$schema" == \#* ]] && continue
  apply_setting "$schema" "$key" "$value"
done < "$KIT_DIR/config/settings.conf"
ok "Theme, cursor, dark mode, window buttons and dock applied"

if [[ -n "$WALLPAPER" ]]; then
  ext="${WALLPAPER##*.}"
  dst="$DATA/backgrounds/ubuntu-mac-kit/wallpaper.${ext,,}"
  place "$WALLPAPER" "$dst"
  apply_setting org.gnome.desktop.background picture-uri "'file://$dst'"
  apply_setting org.gnome.desktop.background picture-uri-dark "'file://$dst'"
  ok "Wallpaper set"
fi

# ---------------------------------------------------------------------------
section "Top bar and apps"

if (( WITH_EXTENSION )); then
  place "$KIT_DIR/extension/$EXT_UUID" "$DATA/gnome-shell/extensions/$EXT_UUID"
  current="$(gsettings get org.gnome.shell enabled-extensions)"
  # Upgrading from 1.0.0: remove the extension installed under its old ID.
  if manifest_has "$DATA/gnome-shell/extensions/$LEGACY_EXT_UUID"; then
    run rm -rf "$DATA/gnome-shell/extensions/$LEGACY_EXT_UUID"
    if [[ "$current" == *"'$LEGACY_EXT_UUID'"* ]]; then
      current="$(without_extension "$current" "$LEGACY_EXT_UUID")"
      run gsettings set org.gnome.shell enabled-extensions "$current"
    fi
  fi
  if [[ "$current" != *"'$EXT_UUID'"* ]]; then
    if [[ "$current" == "@as []" || "$current" == "[]" ]]; then
      updated="['$EXT_UUID']"
    else
      updated="${current%]}, '$EXT_UUID']"
    fi
    apply_setting org.gnome.shell enabled-extensions "$updated"
  fi
  apply_setting org.gnome.shell disable-user-extensions false
  ok "Mac Bar extension installed and enabled"
else
  skip "Mac Bar extension"
fi

if (( WITH_NOTES )); then
  place "$KIT_DIR/apps/desktop-note/note.py" "$DATA/desktop-note/note.py"
  write_file "$CONF/autostart/desktop-note.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Desktop Note
Comment=Transparent sticky notes on the desktop
Exec=env GDK_BACKEND=x11 python3 $DATA/desktop-note/note.py --background
X-GNOME-Autostart-enabled=true
NoDisplay=true
EOF
  if ! python3 -c 'import gi; gi.require_version("Gtk", "3.0")' 2>/dev/null; then
    warn "Sticky Notes needs PyGObject: sudo apt install python3-gi gir1.2-gtk-3.0"
  fi
  ok "Sticky Notes app"
else
  skip "Sticky Notes app"
fi

place "$KIT_DIR/assets/files-folder.svg" "$DATA/icons/ubuntu-mac-kit/files-folder.svg"
if [[ -f /usr/share/applications/org.gnome.Nautilus.desktop ]]; then
  sed "s|^Icon=.*|Icon=$DATA/icons/ubuntu-mac-kit/files-folder.svg|" /usr/share/applications/org.gnome.Nautilus.desktop \
    | write_file "$DATA/applications/org.gnome.Nautilus.desktop"
  ok "Files app uses the blue macOS folder icon"
else
  skip "Files app icon (Nautilus not found)"
fi

# ---------------------------------------------------------------------------
section "Icon lock"

if (( WITH_ICON_LOCK )); then
  place "$KIT_DIR/config/keep-mac-icons" "$BIN/keep-mac-icons"
  run chmod +x "$BIN/keep-mac-icons"
  place "$KIT_DIR/config/keep-mac-icons.service" "$CONF/systemd/user/keep-mac-icons.service"
  if command -v systemctl >/dev/null && run systemctl --user daemon-reload 2>/dev/null; then
    if run systemctl --user enable --now keep-mac-icons.service >/dev/null 2>&1; then
      ok "keep-mac-icons service enabled"
    else
      warn "Could not start keep-mac-icons. It will start on next login."
    fi
  else
    warn "systemd user session not available. The icon lock will not run."
  fi
else
  skip "Icon lock"
fi

# ---------------------------------------------------------------------------
section "Done"
if (( DRY_RUN )); then
  echo "  Dry run finished. Nothing was changed."
else
  echo "  Log out and log back in to load the top bar and refresh every app."
  echo "  To undo: $KIT_DIR/uninstall.sh"
fi
