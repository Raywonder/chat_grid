# Indiginous R524 keyboard-runtime repair receipt

- Date: 2026-07-26
- Published path: `/home/blindsoft/public_html/indiginous`
- Public URL: `https://blind.software/indiginous/`
- Client revision: `R524`
- Recovery backup: `/home/tappedin/.openclaw/workspace/backups/indiginous-before-keyboard-runtime-20260726-011528`

## Repair

- Normal-mode input now receives the complete `ModeInput`, including its web/native source, instead of referencing an out-of-scope `input` value.
- A carried media remote only consumes remote keys after its controls have been explicitly focused with Tab; normal movement/action routing is no longer swallowed while the remote is unfocused.

## Verification

- Client tests: 26 passed.
- ESLint: passed.
- Production build: passed.
- Public `version.js`: R524.
- Public JavaScript and CSS: HTTP 200.
- Public WebSocket `/indiginous/ws`: HTTP 101 upgrade.

The user's authenticated Chrome/VoiceOver session still needs the final hands-on check: press each arrow, then Tab to North/South/East/West and activate each movement button. The server-side browser check cannot prove those physical key events from the user's session.
