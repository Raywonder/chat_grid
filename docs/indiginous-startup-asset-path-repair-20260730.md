# Indiginous startup asset-path repair

Date: 2026-07-30 (America/Chicago)

## Cause

The native Windows client loads `https://blind.software/indiginous/`, but the
live HTML referenced `/assets/...` from the domain root. Those JavaScript and
CSS URLs returned 404, while the correct `/indiginous/assets/...` files were
available. The native shell could therefore open a page but could not load the
shared client or reach its sign-in UI.

## Repair

- Built the current client with `VITE_BASE_PATH=/indiginous/`.
- Staged bundle: `deploy/publish/indiginous-startup-repair-20260730-1/`.
- Published the corrected HTML, current hashed JavaScript/CSS, and version file
  to `/home/blindsoft/public_html/indiginous/`.
- Recovery copy: `/home/tappedin/.openclaw/workspace/backups/indiginous-before-startup-repair-20260730-asset-path/`.

## Verification

- Public page: `https://blind.software/indiginous/?native_client=1` returned HTTP 200.
- HTML now references `/indiginous/assets/index-DxxVwjqW.js` and
  `/indiginous/assets/index-D4XdF8kv.css`.
- Both subpath assets returned HTTP 200 with JavaScript/CSS MIME types.
- The old root-relative JavaScript path returned HTTP 404, confirming the
  client is no longer depending on it.
- `https://blind.software/indiginous/version.js` reports `0.4.16 / R539`.
- `wss://blind.software/indiginous/ws` returned HTTP 101 Switching Protocols.

## Remaining

The installed Windows client was not interactively launched through the
non-interactive VM SSH route in this repair. Close and reopen the desktop
client, or use File > Reconnect, then complete the browser sign-in flow if its
saved session is not restored. The Windows VM and owner laptop user-path test
remain the next platform-specific proof step.
