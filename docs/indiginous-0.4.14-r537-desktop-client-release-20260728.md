# Indiginous Windows 0.4.14 / R537 release receipt

Date: 2026-07-28 (America/Chicago)

## Changes

- Re-arm world keyboard focus after Windows activation, Alt+Tab, minimize/restore, and tray reopening.
- Hide the native File-menu and tray sign-in actions after the embedded client reports an authenticated account.
- Restore the main window before opening Settings from the system tray.
- Add microphone input and speaker output device choices to the native Settings dialog, alongside the existing audio mode, volume, gain, layers, and announcement controls.
- Pass selected device IDs into the embedded web audio session.
- Align native and macOS source metadata with the current 0.4.14/R537 release so stale update metadata cannot be selected.

## Source and tests

- Repository commit: `4633032` (`Fix Indiginous desktop focus and settings`)
- Framework: wxPython Windows desktop client
- Version/revision: `0.4.14` / `R537`
- Linux focused/native suite: 34 passed
- Windows 11 VM suite: 33 passed, 1 skipped
- Shared web client build: passed with the existing chunk-size warning
- Source and artifact preflight: passed
- Build host: `OPENCLAW-WIN11`, Windows 11, Python 3.12.10, PyInstaller 6.21.0, Inno Setup 6.7.3

## Artifact

- Stable filename: `Indiginous_Setup.exe`
- Local artifact: `desktop/wxpython/release/Indiginous_Setup.exe`
- Size: 27,387,915 bytes
- SHA-256: `b75cd73b0e2a995a612cc749e0a8c6f5054cc69e8594840467ab143e912cb9c9`

## Public verification

- Manifest: https://blind.software/downloads/public/7Kp3mN8vQ2xL5rT9cW6yH1/latest-windows.json
- Installer: https://blind.software/downloads/public/7Kp3mN8vQ2xL5rT9cW6yH1/windows
- Both returned HTTP 200.
- Public manifest reports version `0.4.14`, revision `R537`, and filename `Indiginous_Setup.exe`.
- Downloaded public installer size and SHA-256 match the local artifact exactly.
- Previous public installer and manifest were preserved as:
  - `/home/blindsoft/public_html/indiginous/downloads/Indiginous_Setup.exe.bak-20260728-1025-r537-final`
  - `/home/blindsoft/public_html/indiginous/updates/latest-windows.json.bak-20260728-1025-r537-final`

## Remaining verification

The VM build and tests are verified. Automated elevated install-and-launch, authenticated world entry, and real NVDA interaction could not be completed through the available non-interactive SSH route; no installed-app result is claimed from that probe. The published artifact and public download/manifest are verified.

