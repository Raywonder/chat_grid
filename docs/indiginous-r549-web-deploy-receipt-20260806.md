# Indiginous R549 web deployment receipt — 2026-08-06

- Source commit: `163edb6` (`Add background Indiginous auto-updates`).
- Source and web revision: `0.4.18` / `R549`.
- Public URL: `https://blind.software/indiginous/`.
- Public `version.js`: HTTP 200; reports `0.4.18` / `R549`.
- Public entrypoint and hashed JavaScript/CSS assets: HTTP 200.
- Public WebSocket `wss://blind.software/indiginous/ws`: connection accepted with the production origin.
- Client build: Vite production build passed.
- Server tests: `286 passed` from `server/`.
- Native and wxPython Windows/macOS update metadata was checked and reports `0.4.18` / `R549`.
- Rollback tree: `/home/tappedin/backups/indiginous-live-before-r549-20260806-2235`.
- Existing download artifacts and update directories were preserved during the web-only deployment.
