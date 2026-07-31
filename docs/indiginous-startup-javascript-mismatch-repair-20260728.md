# Indiginous startup JavaScript mismatch repair

Date: 2026-07-28 (America/Chicago)

## Cause

The installed Windows client was 0.4.14/R537, while the public `/indiginous/`
page was still serving the older 0.4.13/R536 web bundle. The native client
therefore opened against a stale runtime.

## Repair

- Built the current client with `VITE_BASE_PATH=/indiginous/`.
- Preserved the previous public R536 page, metadata, and assets under:
  `backups/indiginous-before-r537-web-repair-20260728-1225/`.
- Published the validated R537 bundle to `/home/blindsoft/public_html/indiginous/`.

## Proof

- Public version reports 0.4.14/R537.
- `/indiginous/`, its JavaScript, CSS, version, help, and changelog return HTTP 200.
- Downloaded public JavaScript passes `node --check`.
- Public WebSocket returns `101 Switching Protocols` and expects R537.
- No installer or source-tree feature changes were made during this repair.

## User action

Fully exit Indiginous from its tray menu and start it again so WebView2 reloads
the matching R537 page. If a JavaScript error remains, capture its exact text;
the installed client log is under `%LOCALAPPDATA%\\TappedIn\\Indiginous\\chat-grid.log`.
