# Indiginous Windows sign-in race repair — 2026-07-30

## Outcome

The Windows desktop client was rebuilt as version `0.4.16`, revision `R539`, with the browser sign-in callback listener started before the browser is opened. This removes the fast-browser callback race that could leave the client unsigned in.

## Evidence

- Source focused test: `3 passed` (`desktop/wxpython/tests/test_auto_connect.py`)
- Windows test suite: `34 passed, 1 skipped`
- Windows installer build: completed with PyInstaller and Inno Setup
- Artifact: `Indiginous_Setup.exe`
- Artifact size: `27,395,991` bytes
- Artifact SHA-256: `4b59ba02e429cdadcb77295c030fc56ff96a4abc4117352ff46b824f2de348dc`
- Artifact preflight: passed for `0.4.16` / `R539`
- Public update manifest: HTTP 200, `0.4.16` / `R539`
- Public installer: HTTP 200; downloaded SHA-256 matches the manifest exactly
- Recovery backup: `/home/tappedin/.openclaw/workspace/backups/indiginous-before-20260730-login-race-r539`

## Remaining proof

The installer and public update path are verified. Interactive installation, launch, browser return, and successful sign-in on Dominique's physical Windows laptop still require a desktop-control route or Dominique's local launch. The current connected WSL route can reach the VM's SSH/build lane but does not provide Windows GUI control.
