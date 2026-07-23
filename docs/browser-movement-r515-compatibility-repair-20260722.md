# Browser movement compatibility repair

Date: 2026-07-21/22 CDT

## Cause

The account/bookmark compatibility URL `/chatgrid/` was serving client revision
R513 while the current Endiginous URL `/endiginous/` was serving R515. The older
client was therefore not the same browser build that had the current movement
handling and server protocol expectations.

## Repair

- Backed up the previous compatibility tree to:
  `/mnt/backups/chat-grid/chatgrid-live-before-r515-sync-20260721-235811/`
- Published the validated R515 browser artifact to `/chatgrid/`.
- Preserved the existing downloads, updates, and voice directories.
- Left `/endiginous/` on the same R515 client revision.

## Proof

- `https://blind.software/chatgrid/version.js` reports R515.
- `https://blind.software/endiginous/version.js` reports R515.
- Both client HTML pages resolve their current JavaScript and CSS assets with
  HTTP 200.
- Public WebSocket upgrade to `/endiginous/ws` returned `101 Switching
  Protocols`; the server returned `expectedClientRevision: R515` and
  `serverVersion: S424`.
- The browser bundle contains the arrow-key and `update_position` movement
  paths.

## Remaining user-path check

An authenticated browser session still needs to press an arrow and confirm the
position changes in the live dashboard. The stale compatibility artifact that
caused the mismatch is repaired; this receipt does not claim that final
authenticated interaction test was performed.
