# Indiginous R562 Tesla TV official-source release receipt

- Date and node: 2026-09-06 CDT, `tappedin-server` through the Windows Tailscale and SSH path.
- Source code commit: `50b4c9d` (`fix: source Tesla TV from official livestreams`).
- Repository and branch: `/home/tappedin/.openclaw/workspace/projects/chat_grid`, `main`.
- Web release: `0.4.22` / `R562`.
- Public URL: `https://blind.software/indiginous/`.
- User-facing channel name: `Tesla TV`.

## Source and playback proof

- The retired `Tesla Cybercab Live` MP4 loop was removed from the shared TV catalog.
- `Tesla TV` uses the official Tesla YouTube livestream playlist
  `UULV5WjFrtBdufl6CZojX3D8dQ`, owned by verified Tesla channel
  `UC5WjFrtBdufl6CZojX3D8dQ`.
- The browser accepts embeds only for those exact Tesla YouTube identifiers.
- Server metadata also records Tesla's official livestream portal and Tesla
  Investor Relations webcast index as approved Tesla sources.
- Both live TV items hydrated to one `Tesla TV` preset, all copied X/Twitter
  Tesla video URLs were absent, and all three official Tesla source keys were
  present after the service restart.

## Verification

- Client focused tests: 7 passed.
- Client complete test suite: 42 passed.
- TypeScript lint: passed.
- Vite production build: passed.
- Server focused persistence tests: 11 passed.
- Server complete test suite: 295 passed.
- `chat-grid.service`: active after restart; active timestamp
  `2026-09-06 03:33:03 CDT`.
- Public page, `version.js`, and the deployed JavaScript asset each returned
  HTTP 200.
- Public `version.js` reports `0.4.22` / `R562`.
- Deployed asset: `assets/index-DE9yeU_7.js`, 953,925 bytes,
  SHA-256 `ad3b9e863e8b1a4bb5a172ee4622ee1bad10440c06d91095bbe63e1f5654835b`.
- The deployed JavaScript contains the exact official Tesla livestream
  playlist identifier, and the YouTube embed endpoint returned HTTP 200.

## Rollback and retained artifacts

- Web rollback tree:
  `/home/blindsoft/backups/indiginous-live-before-r562-20260906T033256-0500`.
- State rollback file:
  `/home/tappedin/.openclaw/workspace/projects/chat_grid/server/runtime/event-backups/items-before-tesla-tv-r562-20260906T033256-0500.json`.
- Source-file rollback tree:
  `/home/tappedin/.openclaw/backups/chat-grid-tesla-tv-20260906T032456-0500`.
- The existing Windows installer was preserved unchanged at 27,396,416 bytes,
  SHA-256 `e69e6e9674279f31160fdb2e288a283cf36724123368d5ba8703c0cc117e4438`.

## Limitation

The official YouTube player starts muted because browsers block unsolicited
audio. A user can unmute it with the player's controls. The live playlist
advances through Tesla's official archived livestreams when no new live event
is active.
