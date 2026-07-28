# Indiginous 0.4.10 account-download release

Date: 2026-07-26

## Windows build

- Host: `OPENCLAW-WIN11`, `openclaw-win11\\clawadmin`
- Framework: wxPython
- Version/revision: `0.4.10` / `R533`
- Artifact: `Indiginous_Setup.exe`
- Local artifact: `desktop/wxpython/release/Indiginous_Setup.exe`
- SHA-256: `8f75e0a0d5d96aeff6a5875e8ed3ccbf7cbfb3d935a9ca460764572e0de6755d`
- Tests: 24 passed, 1 platform-appropriate skip
- Source and artifact preflight: passed

## Account and public download update

- Updated the active BlindSoftware account page in `/home/blindsoft/public_html/index.php`.
- Account download actions continue to use short-lived account-scoped tokens and
  the stable app-name filename `Indiginous_Setup.exe`.
- Account labels now say “latest” instead of embedding stale version numbers.
- Replaced the stable Windows artifact and `latest-windows.json` manifest.
- Public download URL: `https://blind.software/downloads/public/7Kp3mN8vQ2xL5rT9cW6yH1/windows`
- Public manifest URL: `https://blind.software/downloads/public/7Kp3mN8vQ2xL5rT9cW6yH1/latest-windows.json`
- Both public URLs returned HTTP 200; downloaded installer checksum matched the
  local artifact and manifest.
- Previous live site files were backed up under:
  `/home/tappedin/.openclaw/workspace/backups/indiginous-site-release-20260726-1715/`

The published macOS account links remain pointed at the currently available
stable `Indiginous.dmg` and `Indiginous-macOS.zip` packages (0.4.5) until a
newer signed Mac build is produced.

## Not claimed

- Physical NVDA test on Dominique’s Windows desktop was not performed here.
- No new macOS build or signing operation was performed in this release.
