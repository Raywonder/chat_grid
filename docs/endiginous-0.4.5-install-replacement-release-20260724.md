# Indiginous 0.4.5 install-replacement release

Date: 2026-07-24 CDT
Revision: R517

## Outcome

Indiginous 0.4.5 is published for Windows and macOS. Existing installs now replace the complete application payload during upgrade, so files removed or renamed by newer builds are not left behind. Legacy install directories, shortcuts, and autorun entries are still cleaned by the migration layer, while user data is preserved in the current Indiginous data directory.

## Windows proof

- Build host: approved Windows 11 VM, Windows 11, Python 3.13.14, wxPython 4.2.5.
- Tests: 39 passed.
- Artifact: `desktop/native/windows/release/IndiginousSetup-0.4.5.exe`
- SHA-256: `96f70c6c30d937ce9acdc7c64fd8d5243f5f709cea79f313b10e8ef7633fcae8`
- Artifact and source preflight passed.
- Controlled silent install proved the current install directory's `stale-removed-by-upgrade.txt` was removed and the legacy `%LOCALAPPDATA%\\Programs\\Chat Grid` directory was removed.
- Public URL and downloaded public checksum matched the local artifact.

## macOS proof

- Build host: approved Mac mini, macOS 15.7.7, Xcode available.
- Tests: 38 relevant tests passed; one Windows-only environment test was excluded on macOS because it intentionally simulates Windows `Program Files` roots.
- ZIP: `desktop/native/macos/release/Indiginous-0.4.5-macOS.zip`
- ZIP SHA-256: `81a52a914fb9c4f2e2514a0bf50b8d10621dc12efcba0710fb9c13d2d9a44839`
- DMG: `desktop/native/macos/release/Indiginous-0.4.5.dmg`
- DMG SHA-256: `d9ef2f92589c6bb43a193ae21bb8c5d7a6873a1fed58c24ea1181b8a94afb370`
- A temporary Mac upgrade simulation replaced an old `Indiginous.app` bundle and proved the stale bundle file was absent afterward.
- Artifact preflight passed for both packages.
- Public manifest returned version 0.4.5/R517; both public URLs returned HTTP 200; the downloaded public ZIP checksum matched.

## Recovery

The previous public 0.4.4 Windows and macOS artifacts/manifests are preserved in:

`/home/tappedin/OpenCloud/Agent Reports/Indiginous Backups/indiginous-before-045-20260723/`

