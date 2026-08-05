# Indiginous R523 movement-controls receipt

- Date: 2026-07-26
- Published path: `/home/blindsoft/public_html/indiginous`
- Public URL: `https://blind.software/indiginous/`
- Client revision: `R523`
- Recovery backup: `/home/tappedin/.openclaw/workspace/backups/indiginous-before-r523-movement-controls-20260726-0048`

## Change

Added labeled North, South, East, and West controls that use the same authoritative
movement path as the arrow keys. This gives keyboard and screen-reader users a
usable movement route when Chrome or assistive technology reserves arrow events.
Movement now also reports when the signaling socket is unavailable instead of
silently dropping the update.

## Verification

- Client tests: 26 passed.
- Production build: passed.
- Public version: `R523`.
- Public HTML includes the movement controls.
- Public JavaScript and CSS: HTTP 200.
- Public WebSocket `/indiginous/ws`: HTTP 101 upgrade.

The actual user's Chrome/VoiceOver arrow-event delivery remains unverified because
the paired computer-control route was unavailable during this check.
