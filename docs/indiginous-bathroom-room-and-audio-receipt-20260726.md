# Indiginous bathroom rooms and room audio receipt

Date: 2026-07-26

## Implemented

- `roomLayout=bathroom` now creates a usable generated bathroom interior.
- The default bathroom is shared and usable by all users, including men and
  women. The existing room/door `doorState` remains the privacy control.
- Generated fixtures are server-assigned to the room with `roomId` and
  `roomRole`: toilet, sink, shower, mirror, towel rack, and soap dispenser.
- Generated fixtures and the existing generic place companions are kept inside
  the configured room dimensions.
- Generated bathroom locations advertise `bathroom_tile`; the client uses the
  existing real footstep samples with a tile-specific profile.
- Room entrances now use the real door-open sound. The existing arrival path
  plays the matching door-close sound after a successful transition.
- Client revision advanced from R531 to R532.

## Verification

- Focused server tests: 2 passed
  (`test_community_house_repair_creates_full_interior_and_companions` and
  `test_community_bathroom_room_gets_shared_fixtures_and_tile_footsteps`).
- Python compile check: passed.
- Client production build: passed.
- `git diff --check` on changed paths: passed.

## Remaining limitation

The broader `test_item_schema_ui.py` suite currently has one existing failure
because older `house_object` journal properties (`journalFolder`, etc.) lack
matching property metadata. That failure predates this bathroom change; the
focused room tests and build are green. No production deployment or installer
replacement was performed in this change.
