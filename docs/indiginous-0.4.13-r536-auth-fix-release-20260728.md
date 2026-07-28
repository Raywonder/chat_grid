# Indiginous Windows 0.4.13 / R536 browser sign-in fix

Date: 2026-07-28

## Fix

The wxPython desktop shell now remembers that a browser callback completed and
continues the embedded client's Connect action regardless of the optional
automatic-connect preference. Previously, the callback loaded successfully
but the desktop shell only clicked Connect when that preference was enabled.

## Build proof

- Source tree: `/home/tappedin/.openclaw/workspace/projects/chat_grid`
- Source HEAD at build: `107138b76855e6e1765a54ad87f32795aac7d9ba`
- Framework: wxPython Windows desktop
- Version/revision: 0.4.13 / R536
- Build host: `OPENCLAW-WIN11`, account `clawadmin`
- Windows tests: 29 passed, 1 skipped
- Installer: `Indiginous_Setup.exe`, 27,384,236 bytes
- SHA-256: `9b02ecaedba3f6d3b09d9c4b5c952d602ccfd93c74896bf3bb3766995e01b409`
- Source and artifact preflight: passed

## Public proof

- Tokenized manifest returned HTTP 200 and reports 0.4.13 / R536 with the
  checksum above.
- Tokenized installer returned HTTP 200 with the stable filename
  `Indiginous_Setup.exe`; downloaded bytes matched the checksum above.
- Previous public installer preserved as:
  `/home/blindsoft/public_html/indiginous/downloads/Indiginous_Setup.exe.bak-20260728-0425-auth-fix`
- Previous public manifest preserved as:
  `/home/blindsoft/public_html/indiginous/updates/latest-windows.json.bak-20260728-auth-fix`

## Remaining limitation

The VM's SSH session could not perform an elevated silent install (`Access is
denied`). Installed-file launch, NVDA interaction, and a real authenticated
desktop sign-in therefore remain unverified in this receipt. The old public
artifact remains recoverable from the timestamped backup.
