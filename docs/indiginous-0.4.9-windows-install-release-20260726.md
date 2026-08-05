# Indiginous 0.4.9 Windows release receipt

Date: 2026-07-26
Release: Indiginous 0.4.9 / R531

## Installer

- Artifact: `desktop/wxpython/release/IndiginousSetup-0.4.9.exe`
- Size: 27,372,001 bytes
- SHA-256: `fe0acad37cb33b98b6b1a4883f7916431cb4085570fb6164ade59ef1021e8448`
- Public URL: `https://blind.software/indiginous/downloads/IndiginousSetup-0.4.9.exe`

The installer now defaults to `C:\Program Files\Indiginous`, requires elevation for that machine-wide location, replaces the application payload on upgrade, and removes obsolete Indiginous/Chat Grid application directories and shortcuts. User data is not treated as disposable install payload.

Installers built from this script check the HTTPS update manifest before installing. If a newer Indiginous installer is available, the older installer downloads it, verifies its SHA-256, hands off to it, and exits. A command-line loop guard prevents recursive handoff.

## Proof

- wxPython tests: 18 passed.
- Client tests: 26 passed.
- Client lint and production build: passed.
- Source and artifact release preflight: passed.
- Inno Setup 6.7.3 compile: passed.
- Public page, manifest, and installer: HTTP 200; downloaded public installer hash matched the artifact hash.
- Windows VM install proof: `C:\Program Files\Indiginous\Indiginous.exe` exists, the legacy `C:\Program Files\Indiginous` directory was removed, and the temporary proof task was removed.

The final physical-desktop NVDA/Alt failure test remains to be performed on Dominique's active Windows desktop. The Windows VM proved the install location and legacy Program Files cleanup; per-user legacy cleanup is encoded in the installer and source-checked but was not claimed as a runtime proof under the SYSTEM test context.
