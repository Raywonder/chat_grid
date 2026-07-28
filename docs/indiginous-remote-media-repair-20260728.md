# Indiginous remote radio/TV playback repair — 2026-07-28

## Result

The live Indiginous web client was serving the stale R520 bundle even though the
validated R536 client and matching server were ready. That left remote-control
input and the current media playback recovery path out of sync with production.

The exact public target was backed up and republished from:

`deploy/publish/indiginous-r536-recovery-20260728-0524/`

The stale public assets were removed from the exact `indiginous/assets/` target;
the current public bundle is now R536 / 0.4.13 and is owned by
`blindsoft:blindsoft`.

Recovery copy:

`backups/indiginous-before-remote-media-20260728-093142/`

## Proof

- `https://blind.software/indiginous/` returned HTTP 200.
- Public `version.js` reports `0.4.13` / `R536`.
- Public JavaScript and CSS returned HTTP 200 with the expected MIME types.
- The public bundle contains the remote-control packet, focused-remote controls,
  and active-playback recovery code.
- Public WebSocket upgrade returned `101 Switching Protocols` and advertised
  expected client revision `R536`; server reported `0.4.13 S425`.
- Focused server remote radio/TV tests: 13 passed.
- Both `chat-grid.service` and `chat-grid-companion.service` are active.
- `server/runtime/items.json` is valid JSON.

## Remaining user step

Restart the desktop/browser client or reload Indiginous so it drops any cached
R520 bundle. Then hold the remote, focus its controls with Tab, and try power,
channel, or volume again. The server-side remote handlers were already covered
by the focused tests; this repair corrected the stale client actually being
served to users.
