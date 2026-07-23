# Endiginous macOS unsigned build handoff

Date: 2026-07-21

## Target

- Product: Endiginous
- Version: 0.4.3
- Web revision: R514
- Build type: unsigned internal macOS artifact
- Existing older unsigned artifact: preserved; do not replace until the new artifact passes proof

## Verified here

- Source preflight passed with the `wxpython` framework:
  `python3 scripts/preflight.py source --repo . --framework wxpython --version 0.4.3 --revision R514`
- The current project source is the intended 0.4.3/R514 tree.
- The expected output names are:
  - `desktop/native/macos/release/Endiginous-0.4.3-macOS.zip`
  - `desktop/native/macos/release/Endiginous-0.4.3.dmg`

## Blocker

The connected node list contains one generic `Mac mini` and does not identify Matt's newer M4-or-later Mac as a separate node. The existing development Mac must remain undisturbed, so the build is not being run there. The Linux host cannot produce a valid macOS bundle or DMG.

## Resume command on the newer Mac

```bash
cd /home/tappedin/.openclaw/workspace/projects/chat_grid/desktop/native/macos
PYTHON_BIN=python3 ./scripts/build-macos.sh
```

After the build, run artifact preflight against both ZIP/DMG outputs, compute SHA-256 checksums, launch the unsigned app, verify deep-link/auth return and native menu/VoiceOver behavior, then write the release receipt. Do not update `latest-macos.json` or replace the older download until those checks pass.

## Known release cleanup

- `desktop/native/updates/latest-macos.json` is stale and must not be published from until it matches the new artifact, version, revision, URLs, and checksums.
- `UNSIGNED_BUILD_STATUS.md` is historical and should not be used as the new receipt.
