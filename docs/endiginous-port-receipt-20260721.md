# Endiginous primary-route port receipt

Date: 2026-07-21 CDT

## Verified

- Client source builds with `VITE_BASE_PATH=/endiginous/`.
- Public `https://blind.software/endiginous/` returns HTTP 200 and loads the
  `/endiginous/` JavaScript, CSS, and version assets.
- Public `/endiginous/` and compatibility `/chatgrid/` WebSocket routes both
  complete a `101 Switching Protocols` handshake and return the Endiginous
  auth-required packet.
- Public Endiginous auth and legacy client-auth routes reject malformed
  callbacks with HTTP 400 rather than accepting them.
- Public Windows feed and installer agree on R514 and SHA-256
  `9308b4c74796104b09a70a1087a892315767554cc55d43cbb9cec3fe6b8144ca`.
- Public macOS feed and existing unsigned 0.4.1 DMG/ZIP are available under
  `/endiginous/`; no newer macOS build is claimed here.
- Server service is active on the new `/endiginous/` base path.
- Source preflight passed for wxPython 0.4.3/R514; client lint and 25 Vitest
  tests passed; server focused tests passed 20/20; deep-link/browser-auth
  tests passed 6/6; Python compilation and PHP syntax checks passed.

## Compatibility

The old `/chatgrid/` route, `chatgrid://` deep link, legacy auth route names,
environment names, Python package paths, service names, and persistent storage
identifiers remain intentionally supported for older clients and installed
state. New defaults and visible links use Endiginous.

## Recovery points

- Workspace diff checkpoint: `/tmp/endiginous-preport-20260721.patch`
- Nginx backup: `/etc/nginx/conf.d/000-cpanel-shared-ip-sni.conf.bak-endiginous-*`
- Apache Endiginous include backup: `.../endiginous.conf.bak-endiginous-*`
- BlindSoftware auth/index backups: `/home/blindsoft/public_html/index.php.bak-endiginous-*`

## Remaining limitation

Full wxPython test execution on this server was not possible because the
managed environment attempted to build wxPython and the server has no C
compiler. Windows-native interactive NVDA/UIA proof remains a Windows VM
responsibility; the earlier VM receipt records that limitation.
