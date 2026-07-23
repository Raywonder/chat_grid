# Endiginous R515 auth/world-load receipt

Date: 2026-07-21 CDT

## Change

- Preserved the one-use `external_auth` assertion in session storage until the
  auth result succeeds or fails, so an update/revision reload cannot discard a
  fresh sign-in callback.
- Added an explicit native-shell callback connect kick after the embedded page
  loads. This matters because native mode hides the web connect controls.
- Bumped the client revision to R515.

## Proof

- Client lint passed.
- Client tests passed: 25 tests in 6 files.
- Clean Vite production build passed.
- Published `/endiginous/` reports R515.
- Published HTML references `/endiginous/assets/index-DEZ1zV6t.js` and
  `/endiginous/assets/index-CHvDw-Mp.css`; both returned HTTP 200.
- Public `/endiginous/ws` returned `101 Switching Protocols` and the server
  advertised expected client revision R515.
- Public WebSocket auth challenge identified the unauthenticated state rather
  than a missing or broken world endpoint.

## Recovery

Pre-publish copy:

`/home/tappedin/.openclaw/workspace/projects/chat_grid/recovery/endiginous-r515-20260721-162251/`

## Remaining verification

- The Windows VM is reachable on SSH and RDP, but its encrypted build-share
  credential could not be imported in the current VM session, so interactive
  Windows/NVDA proof remains pending.
- The welcome protocol intentionally sends the authenticated user's current
  location snapshot. A room/house restore can therefore look like a partial
  world even when the server world data is healthy.
