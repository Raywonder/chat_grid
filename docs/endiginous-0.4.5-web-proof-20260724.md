# Endiginous 0.4.5 web proof — 2026-07-24

- Source: `projects/chat_grid`, client `0.4.5`, revision `R518`.
- Client lint passed; web test suite passed: 25 tests.
- Published and checked both `https://blind.software/endiginous/` and the compatibility path `https://blind.software/chatgrid/`.
- Both aliases serve the 0.4.5/R518 version metadata and all referenced JavaScript/CSS/help/changelog/branding assets return HTTP 200.
- The media proxy is present and returns its expected HTTP 401 authentication gate without a session.
- Both public WebSocket endpoints complete a TLS handshake and return `auth_required` with `Endiginous`, release `0.4.5`, expected client `R518`, and server `0.4.5 S424`.
- `chat-grid.service` and `chat-grid-companion.service` are active.
- Windows installer, macOS ZIP, and macOS DMG artifact preflight passed. Public download checksums match the release manifests.
- Recovery backup: `/home/tappedin/OpenCloud/Agent Reports/Endiginous Backups/endiginous-before-web-045-20260724/`.
- Movement repair: initial remote-control focus is now off; carrying a radio/TV remote no longer blocks arrow movement until the user explicitly focuses the remote with `Tab`.
