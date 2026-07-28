# Indiginous vehicle release receipt — 0.4.12 / R535

Date: 2026-07-26/27 CDT

## Delivered

- Added valid Ogg vehicle audio assets for car and SUV idle loops, start, stop, and horn sounds.
- Added vehicle metadata and accessible driving instructions to the shared city vehicles.
- Added server-side blocking when a vehicle would drive into another connected person or occupied vehicle.
- Added explicit vehicle start/stop sound events and local engine-loop lifecycle cleanup on disconnect.
- Suppressed walking-footstep playback while driving and exposed a concise driving status message.
- Bumped the web client metadata to release `0.4.12`, revision `R535`.

## Verification

- `server/.venv/bin/python -m pytest -q server/tests/test_item_persistence.py`: 10 passed.
- Python compilation for the changed server modules passed.
- Client production build passed through `deploy/scripts/deploy_client.sh`.
- Client ESLint passed.
- `git diff --check` passed.
- `chat-grid.service` and `chat-grid-companion.service` are active after the world-service restart.
- Public `https://blind.software/indiginous/` returned HTTP 200.
- Public vehicle asset `https://blind.software/indiginous/sounds/vehicles/car-engine-idle.ogg` returned HTTP 200 with `audio/ogg`.
- Public `version.js` reports `0.4.12` / `R535`.

The public download/update areas were preserved during the client promotion. Windows/macOS desktop packaging and physical screen-reader testing are separate release lanes and were not replaced by this web-world vehicle release.
