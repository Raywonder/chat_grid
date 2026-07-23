# Browser accessibility hardening receipt

Date: 2026-07-22 CDT

## Scope

Continued the existing R516 browser/client work. No duplicate release tree or
public download was created.

## Changes

- Added a persistent, screen-reader-readable world summary tied to the canvas.
- Changed the transient status surface to an atomic `role="status"` live
  region and stopped clearing the last status silently.
- Added `aria-haspopup="dialog"` to the settings trigger.
- Suppressed background focus with `inert` while settings is open and restored
  it on close.
- Made the settings overlay and content scroll safely on smaller screens.
- Hardened the iOS App Store IPA validator so shebang-based test tools work on
  no-execute temporary filesystems while real macOS tools still run directly.

## Verification

- Browser tests: 25 passed.
- Browser lint: passed.
- Browser production build: passed.
- `git diff --check`: passed.
- iOS release-tool tests: 4 files, 28 tests passed.

## Still not a release approval

Authenticated movement, iOS Safari touch/audio-unlock behavior, full browser
audio-layer controls, NVDA/VoiceOver proof, signed artifacts, and published
user-facing verification remain outstanding. Existing public downloads and
update feeds remain unchanged.
