# Asset Licensing and Release Checklist

This document tracks the redistribution status of non-code assets. It is a
release gate, not a claim that every file currently in a private or production
deployment can be republished.

## Known source groups

- `client/public/sounds/device-buttons/`: generated with ElevenLabs on
  2026-07-14. Keep generation receipts and the service terms applicable on the
  generation date with release records.
- `client/public/sounds/clock/archive/`: derived from the approved TappedIn
  archive pack described in `docs/archive-sound-library.md`. Preserve the
  original archive and its owner/permission receipt. Do not publish as a
  general-purpose sound pack without confirming redistribution rights.
- `client/public/sounds/clock/el640/`: review required. Record the original
  voice/source owner and redistribution permission before public packaging.
- `client/public/sounds/radio/relaxation/`: review required. These filenames
  identify longer recordings or programs; do not assume the MIT code license
  covers them.
- `client/public/sounds/radio/station-switch/`: review required for station
  names, voices, and branding even when the cue itself was generated in-house.
- `client/public/sounds/billboards/`: project voice/branding asset. Preserve
  the voice-generation and approved-use receipt; do not treat a person's voice
  or identity as MIT-licensed.
- Other sounds present in the original upstream Git history: covered only to
  the extent the upstream author's MIT declaration was intended to include
  them. Keep the upstream notice and avoid extracting them into a standalone
  asset library without separate confirmation.
- Other newly generated ambience, action, reaction, house, door, portal, and
  interface cues: record generator/source, date, operator, prompt or source
  reference, and permitted distribution before the next public package.

## Before a public web or desktop release

1. Inventory every bundled non-code file and hash it.
2. Record its source, creator/provider, creation or acquisition date, and
   permitted uses.
3. Exclude or replace anything whose redistribution basis is unclear.
4. Preserve required attribution and license texts in the web deployment and
   every desktop installer/application bundle.
5. Review names, logos, voices, station IDs, feeds, and cultural references
   separately from code copyright.
6. Save the resulting manifest and receipts with the release artifacts.

Remote streams and live feeds should normally remain URLs resolved at runtime,
not copied media. Their providers' terms still apply, and Chat Grid must not
imply that it owns or relicenses their content.
