#!/usr/bin/env bash
# Builds the release bundle dist/ubuntu-mac-kit.tar.gz for GitHub Releases.
#
# The bundle is this repository plus a payload/ folder with the third-party theme files,
# taken from a machine where the finished theme is installed:
#   ~/.local/share/icons/WhiteSur         WhiteSur icon theme (base)
#   ~/.local/share/icons/WhiteSur-dark    WhiteSur dark, with folders and file icons from mac-file-icons-gen.py
#   ~/.local/share/icons/macOS            apple_cursor (macOS)
#   ~/.config/gtk-4.0/                    MacTahoe libadwaita styling (gtk.css, gtk-dark.css, assets)
#
# Usage: tools/build-bundle.sh [icons_dir] [gtk4_dir]
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ICONS="${1:-$HOME/.local/share/icons}"
GTK4="${2:-$HOME/.config/gtk-4.0}"
DIST="$REPO/dist"
OUT="$DIST/ubuntu-mac-kit"

for need in "$ICONS/WhiteSur" "$ICONS/WhiteSur-dark" "$ICONS/macOS" "$GTK4/gtk.css"; do
  [[ -e "$need" ]] || { echo "Missing $need" >&2; exit 1; }
done

rm -rf "$DIST"
mkdir -p "$OUT"

# Repository files at HEAD (uncommitted changes are not included)
git -C "$REPO" archive HEAD | tar -x -C "$OUT"
rm -rf "$OUT/.github" "$OUT/docs/media"

mkdir -p "$OUT/payload/icons" "$OUT/payload/gtk-4.0" "$OUT/payload/licenses"
for theme in WhiteSur WhiteSur-dark macOS; do
  cp -a "$ICONS/$theme" "$OUT/payload/icons/"
  rm -f "$OUT/payload/icons/$theme/icon-theme.cache"
done
for item in gtk.css gtk-dark.css assets windows-assets; do
  if [[ -e "$GTK4/$item" ]]; then cp -a "$GTK4/$item" "$OUT/payload/gtk-4.0/"; fi
done
cp "$REPO/LICENSE" "$OUT/payload/licenses/GPL-3.0.txt"
cp "$REPO/THIRD_PARTY.md" "$OUT/payload/licenses/"

tar -C "$DIST" -czf "$DIST/ubuntu-mac-kit.tar.gz" ubuntu-mac-kit
(cd "$DIST" && sha256sum ubuntu-mac-kit.tar.gz > ubuntu-mac-kit.tar.gz.sha256)

du -sh "$DIST/ubuntu-mac-kit.tar.gz"
cat "$DIST/ubuntu-mac-kit.tar.gz.sha256"
