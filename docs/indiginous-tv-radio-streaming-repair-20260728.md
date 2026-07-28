# Indiginous TV/radio streaming repair

Date: 2026-07-28

## Cause

The public client entry point was serving an older R520 bundle while the
current client was R537. In addition, the living-room TV's default channels
pointed at AAAStreamer station pages that currently return HTTP 404 rather
than a playable media stream. The TV was also in a separate media group from
the room speaker radios.

## Repair

- Published the validated R537 web client to the canonical `/indiginous/`
  target (the `/chatgrid/` compatibility route now serves the same bundle).
- Changed the built-in living-room TV defaults to direct, verified playable
  audio sources rather than provider HTML pages.
- Linked the TV to `raywonder-house-radios` so the existing spatial room
  speaker components receive the TV audio.
- Preserved the previous public TV files in
  `backups/indiginous-before-station-playback-20260728-1800/`.

## Proof

- `server/.venv/bin/python -m pytest -q server/tests/test_item_persistence.py server/tests/test_media_guide.py` — 11 passed.
- `python3 -m compileall -q server/app` — passed.
- `git diff --check` — passed.
- `chat-grid.service` restarted and is active.
- Runtime TV state now uses NPR Program Stream, the `raywonder-house-radios`
  group, and direct preset URLs.
- `https://blind.software/indiginous/version.js` reports release 0.4.14,
  revision R537.
- `https://npr-ice.streamguys1.com/live.mp3` returned HTTP 200 and
  `audio/mpeg` during verification.

The provider TV guide entries remain catalog/guide metadata; they are not
treated as playable streams until a provider supplies a direct media URL.
