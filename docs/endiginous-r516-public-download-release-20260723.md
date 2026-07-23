# Endiginous R516 public download release

Date: 2026-07-23 CDT
Source commit: `cf4bdf4` (`Stabilize Endiginous browser and desktop clients`)
Browser release: `0.4.4 / R516`

## Published and verified

- Browser: `https://blind.software/endiginous/` returned HTTP 200 and served
  version `0.4.4 / R516`.
- Windows installer: `EndiginousSetup-0.4.4.exe` returned HTTP 200, size
  27,376,460 bytes, SHA-256
  `732a7aee35018a0cfdb1b091e2bbf8425206bcbcc7196eb61a3e6e505b2ec32a`.
- Windows update manifest returned HTTP 200 and matches the installer name,
  version, revision, URL, and checksum.
- macOS manual-test downloads returned HTTP 200:
  - `Endiginous-0.4.4.dmg` SHA-256
    `352d4883f9d89ff2b414499188b6410451568cb6e4f722bab63b08cf30faa3d6`.
  - `Endiginous-0.4.4-macOS.zip` SHA-256
    `f5cb2cc81a67f7743d1df297eb00d82ea9af415c3530a4fbb6083cbfcc0a670b`.
- BlindSoftware download routing was updated to point authenticated Windows
  and macOS download buttons at the 0.4.4 artifacts. PHP syntax validation
  passed.

## Deliberately not changed

- `latest-macos.json` remains on the prior automatic-update metadata because
  the 0.4.4 Mac artifacts are unsigned and still need Dominique's Mac mini
  VoiceOver/authenticated-world test. The 0.4.4 Mac files are available for
  manual testing only until that proof is complete.
- Existing public files were backed up at:
  `/home/tappedin/.openclaw/workspace/recovery/endiginous-public-before-r516-20260723-0040/`.
