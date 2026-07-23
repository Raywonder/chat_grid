# Endiginous R517 public release — 2026-07-23

## Change

Published the verified Endiginous web client movement repair from commit
`ec2f10b` (`Repair Endiginous movement after stale UI focus`). Hidden or stale
Connect/focus controls no longer prevent world-key recovery to the canvas.

## Build and source proof

- Client tests: 6 files, 25 tests passed.
- Client lint and production build passed.
- Public client revision: `R517`.
- Public release version: `0.4.4`.
- Recovery copy: `/home/tappedin/OpenCloud/Agent Reports/Endiginous Backups/endiginous-before-r517-20260723`.

## User-facing proof

- `https://blind.software/chatgrid/` asset graph passed, including the
  version, branding, help, and changelog resources.
- `https://blind.software/chatgrid/version.js` reports `R517`.
- `https://blind.software/chatgrid/client_branding.json` identifies the
  product as `Endiginous`.
- A real WebSocket connection to
  `wss://blind.software/chatgrid/ws` opened successfully and returned the
  authentication challenge with `expectedClientRevision: R517` and
  `gridName: Endiginous`.
- `chat-grid.service` and `chat-grid-companion.service` are active.
- Server runtime item data parsed successfully with 210 entries.

The public deployment preserved the existing `downloads/`, `updates/`, and
`voice/` trees. The prior public client was retained in the recovery copy.
