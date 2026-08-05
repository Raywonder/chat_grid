# Indiginous client reconnect and release verification

Date: 2026-07-28

## Result

The owner Windows laptop is running Indiginous 0.4.16. Its installed Windows
installer is the same artifact already published in the site downloads area:

- Version/revision: 0.4.16 / R539
- Installer SHA-256: `1638cb3283eae7d37be559fa2100d7bc7177d893f71fd884d231c601240fb066`
- Installed executable: `C:\Program Files\BlindSoftware\Indiginous\Indiginous.exe`
- Running process was verified on the owner laptop as PID 24332.

The public Windows manifest and download hash match that installed build, so
the download was not replaced with a different artifact.

## Reconnect repair

The web client could leave its reconnect state locked if `connect()` rejected
inside the retry loop. Each attempt now catches that failure and continues
through the bounded retry sequence. The reconnect-in-flight flag is also
cleared before a recovery page refresh, so a failed or delayed navigation does
not permanently suppress later retries.

## Published web client

The public web bundle was rebuilt and published as 0.4.16 / R539 after backing
up the previous live directory to:

`/home/tappedin/.openclaw/workspace/backups/indiginous-web-r539-20260728-183113`

Verified from the public side:

- `https://blind.software/indiginous/version.js` reports 0.4.16 / R539.
- The public page and referenced JavaScript/CSS assets return HTTP 200.
- The Windows manifest reports 0.4.16 / R539.
- The public Windows installer hash matches the installed laptop artifact.

## Checks

- Client tests: 28 passed.
- ESLint: passed.
- Production Vite build: passed.
- `git diff --check`: passed.

The complete cross-platform release preflight still reports older metadata in
the separate native/macOS source trees. This receipt therefore claims the
verified Windows artifact and matching web client, not a new macOS release.
