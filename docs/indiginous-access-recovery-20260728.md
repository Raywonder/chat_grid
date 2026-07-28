# Indiginous access recovery — 2026-07-28

## Result

Restored the legacy `/chatgrid/` entry point by redirecting it to the current
canonical `/indiginous/` client. The old page referenced root-relative assets
that returned HTTP 404, so it could not start in a browser or desktop WebView.

## Proof

- `https://blind.software/chatgrid/` returns HTTP 302 to `/indiginous/`.
- Canonical JavaScript, CSS, and `version.js` return HTTP 200.
- A real `wss://blind.software/indiginous/ws` client connection opened.
- `chat-grid.service` and `chat-grid-companion.service` are active.
- The published canonical client remains R536; no source tree or world state
  was rebuilt or replaced during this recovery.

## Recovery point

The active Nginx configuration backup is:

`/etc/nginx/conf.d/000-cpanel-shared-ip-sni.conf.bak-chatgrid-compat-20260728-0348`

Nginx configuration validation passed before reload. Existing deprecation and
duplicate-server warnings remain unrelated to this route change.
