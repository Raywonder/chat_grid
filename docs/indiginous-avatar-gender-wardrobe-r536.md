# Indiginous avatar identity and wardrobe change — 0.4.13 / R536

Date: 2026-07-27

## Implemented

- BlindSoftware's verified `gender` field is now included in the signed
  Indiginous external-auth assertion.
- Indiginous persists account gender, a starter wardrobe, and worn-clothing
  state server-side.
- Avatar gender and worn clothing are included in welcome, movement/location,
  and avatar-update packets, so the identity follows a user between rooms.
- The canvas avatar now presents gender and worn-clothing state, with an
  un-dressed base appearance when clothing is removed.
- Bedrooms receive a generated Wardrobe house object for changing/storage.
- Added `/clothes`, `/wear <item>`, `/remove <item>`, and `/undress` commands.
  The server validates wardrobe membership and broadcasts the result.
- Added the wardrobe object kind and updated user help/documentation.

## Verification

- `python3 -m compileall -q server/app` passed.
- Focused server tests: 31 passed.
- Full client Vitest suite: 27 passed.
- Client production build passed and emitted a new R536 bundle.
- PHP syntax check passed for `/home/blindsoft/public_html/index.php` after
  the assertion change.
- `git diff --check` passed for the touched source paths.

## Remaining release gate

This change is source-built but not deployed or published as a new Windows
installer in this turn. The full server suite reached 269 passing tests but
also reported two existing unrelated failures in the dirty R535 worktree:
`test_ui_definitions_are_complete_for_all_item_types` and
`test_guarded_house_denial_knocks_outside_and_inside`. They must be resolved
or explicitly accepted before a production server restart or installer
release.
