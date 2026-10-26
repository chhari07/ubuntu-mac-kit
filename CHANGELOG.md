# Changelog

All notable changes to this project are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-10-26

### Changed

- Mac Bar extension ID is now `macbar@ubuntu-mac-kit` (was `macbar@aman.local`). Upgrading from 1.0.0 removes the
  old extension automatically.
- Sticky Notes application ID is now `io.github.chhari07.DesktopNote`.
- Mac Bar declares support for GNOME Shell 46, 47 and 48. GNOME 46 remains the tested version.
- The installer accepts GNOME Shell 46 to 48 without `--force-extension`.
- README opens with a before-and-after preview animation and links the 1080p walkthrough video.
- `make_video.py` can render 1080p with burned-in captions, a closing card and an `.srt` file.

## [1.0.0] - 2026-10-26

### Added

- `install.sh` with dry-run mode, confirmation prompt and optional components.
- `uninstall.sh` that restores the previous settings and files from the install backup.
- WhiteSur-dark icons with generated macOS folder and file icons, macOS cursor, MacTahoe GTK 4 styling.
- Mac Bar GNOME Shell extension and the Sticky Notes app.
- `keep-mac-icons` user service that keeps the icon theme selected.
- Release bundle builder, design tokens and an install walkthrough video.
