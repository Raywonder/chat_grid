# Indiginous media catalog and Remote Speaker contract

## Implemented

- Radio presets now include optional categories and four additional public streams:
  Radio Paradise, SomaFM Groove Salad, KEXP 90.3 FM, and WWOZ New Orleans.
- Shared TV presets now carry categories such as News, Entertainment, Documentary,
  Movies, and General.
- A held radio or TV remote now has an accessible guide action. Focus the remote,
  press `G`, or choose `Open media guide` from the command palette. The server
  returns grouped stations/channels and TV provider-guide sources.
- Media items accept `roomImpulseUrl` and `speakerProfile`. Reverb uses the
  generated impulse immediately, then replaces it with a same-origin reviewed
  impulse supplied by a Remote Speaker export when available. Failed or missing
  assets safely retain the generated fallback.

## Remote Speaker handoff

The prepared Remote Speaker application was not present in the server-mounted
OpenCloud tree during this pass, and its Mac-side file route required an
additional operator scope. No unverified asset was copied or published.

The intended export shape is a same-origin audio file referenced by
`roomImpulseUrl`, plus a stable `speakerProfile` name. This keeps the world
runtime independent of the app while allowing official room/device impulses,
speaker cabinets, and future per-environment profiles to be added when the
prepared files are reachable.

## Verification

- `uv run --project server pytest -q server/tests/test_item_persistence.py server/tests/test_radio_station_validator.py`: 21 passed.
- `npm test`: 27 passed.
- `npm run lint`: passed.
- `npm run build`: passed; Vite emitted only the existing chunk-size warning.
- `python3 -m compileall -q server/app`: passed.

This change is catalog/runtime groundwork. It does not claim that the
Mac-side Remote Speaker assets have been imported or that a new release has
been published.
