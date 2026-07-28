# Indiginous R525 ambience playback repair receipt

- Date: 2026-07-26
- Published path: `/home/blindsoft/public_html/indiginous`
- Public URL: `https://blind.software/indiginous/`
- Client revision: `R525`
- Recovery backup: `/home/tappedin/.openclaw/workspace/backups/indiginous-before-ambience-r525-20260726-032714`

## Repair

- Initial `AudioContext.resume()` rejection during login/autoplay policy no longer aborts ambience graph creation.
- Keyboard input now re-primes the listener-local audio context, so Tab/arrows can unlock ambience for screen-reader and keyboard users who never generate a pointer event.

## Verification

- Client tests: 26 passed.
- ESLint: passed.
- Production build with `VITE_BASE_PATH=/indiginous/`: passed.
- Public `version.js`: R525.
- Public JavaScript and CSS: HTTP 200.
- Public `bedroom_quiet.ogg`: HTTP 200.

The final hearing check still belongs to the authenticated Chrome session: hard-refresh Indiginous, press Tab or an arrow, and confirm the room bed is audible.
