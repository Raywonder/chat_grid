# Indiginous Windows 0.4.16 / R539 startup JavaScript repair

Date: 2026-07-28 (America/Chicago)

## Cause

The 0.4.15 client logged a failed `focus-world` JavaScript bridge call during
the delayed startup focus callback. wxPython surfaced that WebView2 timing
failure as the blank `Error running JavaScript:` message. The world page was
not the failing component.

## Fix

- Removed the redundant delayed DOM click from native focus restoration.
- Kept native WebView focus restoration for Alt+Tab and minimize/restore.
- Kept the page-load focus path, which waits for the world focus control before
  activating it.
- Retained guarded native JavaScript bridge logging for future diagnosis.

## Proof

- Commit: `095a8a6` (`Fix Indiginous startup JavaScript focus race`)
- Windows 11 VM tests: 33 passed, 1 skipped.
- Windows installer build completed successfully on `OPENCLAW-WIN11`.
- Installer SHA-256: `1638cb3283eae7d37be559fa2100d7bc7177d893f71fd884d231c601240fb066`
- Installer size: 27,389,926 bytes.
- Laptop install hash matched the VM artifact.
- Laptop launched `Indiginous 0.4.16` twice after installation.
- The laptop log contains no new JavaScript bridge failure or startup
  JavaScript error after either 0.4.16 launch; the only matching failure is
  the historical 0.4.15 entry.
- Public manifest and installer both return HTTP 200, report `0.4.16` / `R539`,
  and the downloaded installer matches the published SHA-256.

Previous public installer and manifest were preserved with the
`20260728-1253-r537-js-error` backup suffix.

## Remaining note

The installed client is verified to start without the reported error. An
authenticated world-entry and NVDA interaction pass was not performed in
this repair check.
