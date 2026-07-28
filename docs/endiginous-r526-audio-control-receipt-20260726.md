# Indiginous R526 room-audio control receipt

- Date: 2026-07-26
- Published path: `/home/blindsoft/public_html/indiginous`
- Public URL: `https://blind.software/indiginous/`
- Client revision: `R526`
- Recovery backup: `/home/tappedin/.openclaw/workspace/backups/indiginous-before-audio-control-r526-20260726-033306`

## Repair

- Added a visible, keyboard-accessible **Start room audio** button.
- The button explicitly resumes the browser audio context and rebuilds the current location ambience graph.
- Status now says whether room ambience is playing or still waiting for browser permission.

## Verification

- Client tests: 26 passed.
- ESLint: passed.
- Production build with `VITE_BASE_PATH=/indiginous/`: passed.
- Public `version.js`: R526.
- Public page, JavaScript, CSS, and `bedroom_quiet.ogg`: HTTP 200.

Final hands-on proof: after a hard refresh in the authenticated Chrome session, Tab to **Start room audio** and activate it; the status should announce that room ambience is playing.
