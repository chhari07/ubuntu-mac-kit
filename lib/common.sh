# shellcheck shell=bash
# Shared helpers for install.sh and uninstall.sh. Sourced, not executed.
# The variables below are used by the scripts that source this file.
# shellcheck disable=SC2034

KIT_NAME="Ubuntu Mac Kit"
KIT_VERSION="1.0.0"
RELEASES_URL="https://github.com/chhari07/ubuntu-mac-kit/releases/latest"
EXT_UUID="macbar@aman.local"

DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}"
BIN="$HOME/.local/bin"
STATE="$DATA/ubuntu-mac-kit"
BACKUP="$STATE/backup"
MANIFEST="$STATE/manifest"            # lines: "created <path>" or "replaced <path>"
SETTINGS_BACKUP="$STATE/settings.backup"  # lines: "<schema> <key> <original value>"

DRY_RUN=0
ASSUME_YES=0

if [[ -t 1 ]]; then
  BOLD=$'\e[1m' DIM=$'\e[2m' GREEN=$'\e[32m' YELLOW=$'\e[33m' RED=$'\e[31m' RESET=$'\e[0m'
else
  BOLD='' DIM='' GREEN='' YELLOW='' RED='' RESET=''
fi

section() { printf '\n%s==> %s%s\n' "$BOLD" "$1" "$RESET"; }
ok()      { printf '  %s[ok]%s    %s\n' "$GREEN" "$RESET" "$1"; }
skip()    { printf '  %s[skip]%s  %s\n' "$DIM" "$RESET" "$1"; }
warn()    { printf '  %s[warn]%s  %s\n' "$YELLOW" "$RESET" "$1" >&2; }
die()     { printf '%s[error]%s %s\n' "$RED" "$RESET" "$1" >&2; exit 1; }

# Run a command, or only print it with --dry-run.
run() {
  if (( DRY_RUN )); then
    printf '  %s[dry-run]%s %s\n' "$DIM" "$RESET" "$*"
  else
    "$@"
  fi
}

confirm() {
  (( ASSUME_YES )) && return 0
  local reply
  read -r -p "$1 [y/N] " reply
  [[ "$reply" =~ ^[Yy]([Ee][Ss])?$ ]]
}

has_key() {
  gsettings list-keys "$1" 2>/dev/null | grep -qx "$2"
}

require_user() {
  [[ $EUID -ne 0 ]] || die "Run this as your normal user, not with sudo. Everything installs into your home folder."
  command -v gsettings >/dev/null || die "gsettings was not found. This kit needs a GNOME desktop."
}

manifest_has() {
  [[ -f "$MANIFEST" ]] && grep -qxF -e "created $1" -e "replaced $1" "$MANIFEST"
}
