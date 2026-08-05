# Indiginous R541 updater-feed repair

Date: 2026-08-04

## Problem

The Windows update manifests named the stable installer `Indiginous_Setup.exe`
with an extra `i`. The updater correctly accepts only the canonical
`Indiginous_Setup.exe`, so an installed client could detect the feed but reject
the published update before downloading it.

## Repair

- Corrected both repository Windows manifests to `Indiginous_Setup.exe`.
- Corrected the release preflight filename gate to enforce the same name.
- Preserved the previous live manifest as
  `/home/blindsoft/public_html/indiginous/updates/latest-windows.json.bak-updater-filename-20260804-1031`.
- Published the corrected manifest to the live BlindSoftware update feed.
- No installer bytes were replaced: the current R541 installer already matched
  the published checksum.

## Proof

- Version/revision: `0.4.18` / `R541`
- Artifact: `Indiginous_Setup.exe`, 27,396,930 bytes
- SHA-256: `3c27b2080b76caceddb9d10392a40d2735e356cc90a693e12ed20af2b487057c`
- Public manifest: HTTP 200; filename, version, revision, and checksum match
- Public installer: HTTP 200; downloaded bytes match the checksum
- Updater simulation from current version `0.4.17`: detected R541, downloaded the
  installer, and verified the checksum
- Source preflight: passed for wxPython 0.4.18/R541
- Artifact preflight: passed
- wxPython updater/accessibility tests: 19 passed
- Native updater/accessibility tests: 12 passed

Physical Windows install/update interaction remains outside this Linux host's
available GUI control path.
