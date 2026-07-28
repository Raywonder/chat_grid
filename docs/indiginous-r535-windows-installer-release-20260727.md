# Indiginous Windows installer release — 0.4.12 / R535

Date: 2026-07-27

The public Windows installer had remained on 0.4.11 / R534 while the web
client and current source had advanced to R535. A clean staging copy of the
current source was aligned to 0.4.12 / R535 and built on `OPENCLAW-WIN11`.

## Proof

- Windows client tests: 27 passed, 1 skipped.
- PyInstaller 6.21.0 completed on Windows 11.
- Inno Setup 6.7.3 completed successfully.
- Artifact: `Indiginous_Setup.exe`, 27,385,701 bytes.
- SHA-256: `1e4d850792f4e0f310d6fb81dfcf90037cef460aebb589efb35eb15474b7e8e4`.
- Public update manifest reports 0.4.12 / R535 and the same checksum.
- Public tokenized installer download returned HTTP 200 and the downloaded
  checksum matched the VM artifact.
- Public `/indiginous/version.js` reports 0.4.12 / R535.

Public installer URL:

`https://blind.software/downloads/public/7Kp3mN8vQ2xL5rT9cW6yH1/windows`

The previous R534 installer and manifest remain as timestamped backups under
`/home/blindsoft/public_html/indiginous/`.

## Remaining limitation

The VM's non-interactive silent-install attempt was blocked by its elevation
context before producing installed-file proof. A physical Windows install,
NVDA interaction, and authenticated world/audio session remain separate
user-device checks.
