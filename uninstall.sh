#!/usr/bin/env bash
# Ubuntu Mac Kit uninstaller.
# Restores the settings and files that install.sh backed up, then removes what it added.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$KIT_DIR/lib/common.sh"

usage() {
  cat <<EOF
$KIT_NAME $KIT_VERSION uninstaller

Usage: ./uninstall.sh [options]

Options:
  -y, --yes       Do not ask for confirmation
  -n, --dry-run   Show what would be done without changing anything
  -h, --help      Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes) ASSUME_YES=1 ;;
    -n|--dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "Unknown option: $1" ;;
  esac
  shift
done

require_user
[[ -f "$MANIFEST" || -f "$SETTINGS_BACKUP" ]] || die "Nothing to undo: $KIT_NAME is not installed for this user."

printf '%s%s %s%s\n\n' "$BOLD" "$KIT_NAME" "$KIT_VERSION" "$RESET"
echo "This restores your settings from before the install and removes the kit's files."
(( DRY_RUN )) && echo "Dry run: nothing will be changed."
echo
confirm "Continue?" || { echo "Cancelled."; exit 1; }

# ---------------------------------------------------------------------------
section "Icon lock"

# Stop the lock first, otherwise it would put the icon theme straight back.
if command -v systemctl >/dev/null && systemctl --user cat keep-mac-icons.service >/dev/null 2>&1; then
  run systemctl --user disable --now keep-mac-icons.service >/dev/null 2>&1 || true
  ok "keep-mac-icons service stopped"
else
  skip "keep-mac-icons service not running"
fi

# ---------------------------------------------------------------------------
section "Desktop settings"

if [[ -f "$SETTINGS_BACKUP" ]]; then
  while read -r schema key value; do
    [[ -z "$schema" ]] && continue
    has_key "$schema" "$key" || continue
    if [[ "$schema $key" == "org.gnome.shell enabled-extensions" ]]; then
      # Only take Mac Bar out, so extensions enabled since the install stay on.
      current="$(gsettings get org.gnome.shell enabled-extensions)"
      updated="$(printf '%s' "$current" | sed -e "s/, '$EXT_UUID'//; s/'$EXT_UUID', //; s/'$EXT_UUID'//")"
      [[ "$updated" == "[]" ]] && updated="@as []"
      run gsettings set org.gnome.shell enabled-extensions "$updated"
    else
      run gsettings set "$schema" "$key" "$value"
    fi
  done < "$SETTINGS_BACKUP"
  ok "Previous settings restored"
else
  skip "No settings backup found"
fi

# ---------------------------------------------------------------------------
section "Files"

if [[ -f "$MANIFEST" ]]; then
  # Undo in reverse order of installation.
  tac "$MANIFEST" | while read -r action path; do
    [[ -n "$path" ]] || continue
    run rm -rf "$path"
    if [[ "$action" == replaced && ( -e "$BACKUP/files$path" || -L "$BACKUP/files$path" ) ]]; then
      run mv "$BACKUP/files$path" "$path"
    fi
  done
  run rmdir --ignore-fail-on-non-empty "$DATA/icons/ubuntu-mac-kit" "$DATA/desktop-note" \
    "$DATA/backgrounds/ubuntu-mac-kit" 2>/dev/null || true
  if command -v systemctl >/dev/null; then
    run systemctl --user daemon-reload 2>/dev/null || true
  fi
  ok "Kit files removed and replaced files restored"
fi

run rm -rf "$STATE"

section "Done"
if (( DRY_RUN )); then
  echo "  Dry run finished. Nothing was changed."
else
  echo "  Log out and log back in to finish."
fi
