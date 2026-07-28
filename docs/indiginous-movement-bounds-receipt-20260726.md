# Indiginous movement-bounds repair — 2026-07-26

## Cause

Location handoff packets did not carry the destination room's effective width
and height. After leaving a smaller house room, the browser retained the old
room bounds and treated valid outside squares as unavailable. Entering a small
room could likewise leave the browser believing the larger previous area was
usable until the server rejected those moves.

The movement display also rendered the raw animated teleport coordinates, which
could expose floating-point noise as long, impossible-looking square values.

## Change

- `location_changed` now carries effective `width` and `height`.
- The client applies those dimensions on every location handoff and clamps the
  received arrival coordinate to them.
- Step-path and nearby-user movement checks use the active location's bounds.
- The dashboard formats animated coordinates instead of exposing raw floating
  point values.

## Proof

- Server focused handoff tests: 4 passed.
- Client test suite: 26 passed.
- Client production build: passed.
- Python compile check: passed.
- Public `/indiginous/` HTML, JavaScript, CSS, auth-start link, and version
  resources: HTTP 200.
- Public WebSocket `wss://blind.software/indiginous/ws`: HTTP 101.
- `chat-grid.service` and `chat-grid-companion.service`: active after restart.
- `server/runtime/items.json`: valid JSON, 214 items.

## Notes

The broader legacy server-message test file still contains one unrelated
pre-existing guarded-house permission failure; it was not introduced by this
bounds repair. The physical Windows/NVDA path was not used for this web-world
repair.
