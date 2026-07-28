# Indiginous name cutover — 2026-07-26

The current product name is `Indiginous` and the canonical web path is
`/indiginous/`. Active client source, web assets, server configuration,
installer metadata, update manifests, and download names use that spelling.

Older spellings remain only in narrowly scoped migration/installer cleanup
lists and server compatibility routing. They are not current product labels.
Those compatibility paths resolve internally to the canonical release so old
installed clients and installers can still update.

## Proof

- Canonical page: `https://blind.software/indiginous/` — HTTP 200, title
  `Indiginous`.
- Version endpoint: `/indiginous/version.js` — version `0.4.9`, revision `R531`.
- Current installer: `IndiginousSetup-0.4.9.exe` — HTTP 200.
- Installer SHA-256:
  `4901baf62af0d5ed1b5a647d6f106b041afc8703bb6939390835dfe136fe8f50`.
- Canonical and legacy update manifest paths return the same current manifest.
- Windows 11 VM build: 18 wxPython tests passed and Inno Setup completed.
- Windows VM install proof: canonical executable exists under
  `C:\Program Files\Indiginous`; legacy `Endiginous` and `Indigenous`
  program folders were removed.
- Python compile check passed for migration and startup modules.

The physical Windows desktop NVDA/Alt keyboard-safety test remains separate
from this naming/install verification and still needs to be performed on the
actual desktop.
