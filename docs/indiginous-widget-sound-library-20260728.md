# Indiginous widget sound library work

## Implemented locally

- Widget sound fields can browse the authenticated sound catalog instead of only accepting `none` or free text.
- The catalog includes packaged audio files discovered under every public `sounds/` folder, plus existing ambience entries.
- A picker can choose a library sound, enter an external URL, or upload a custom loop through the existing checked upload stream.
- Emitted widgets accept up to six references separated by `||`; the seventh selection is rejected without silently dropping an older selection.
- Added `repeat` and `shuffle` loop modes and a bounded fade-between-tracks setting.
- Sound references reject `data:` and `blob:` values for widget updates.

## Verification

- `python3 -m compileall -q server/app` passed.
- `npm run lint` passed.
- `npm run build` passed.
- `uv run pytest -q tests/test_widget_sound_tracks.py` passed: 2 tests.
- Existing `tests/test_item_schema_ui.py` still has the prior unrelated `roomImpulseUrl` metadata failure.

## Not published yet

The current picker is still a keyboard/status-mode flow. Before a release, replace the mixed sentinel list with an accessible grouped DOM picker containing labeled Library, External URL, and Upload sections, explicit preview/stop, six-row playlist management, and keyboard/screen-reader verification on Windows and macOS. The current transition is intentionally described as a fade between tracks, not a true overlapping crossfade.
