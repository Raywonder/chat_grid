# Indiginious authenticated homecoming

Date: 2026-07-28

## What changed

Added `/home`, `/bed`, `/rest`, `/go-home`, and `/gohome` chat commands to the
world server. They only work for a signed-in account authorized by the
Raywonder house alarm.

The route is deliberately layered:

1. If already in the bedroom, settle the user onto the real bedroom bed.
2. If inside another Raywonder room, move to the bedroom.
3. From another location, use an open Houses portal when one is available.
4. If no portal is available, use the verified resident return route, walk to
   the house alarm, authenticate the signed-in identity, enter the house, and
   continue to the bedroom.

The final posture is server-authoritative `lying` on
`seed-raywonder-bedroom-bed`. Unauthorized identities are refused without
movement.

## Proof

- Focused home/house tests: 4 passed.
- Python syntax check: passed for `server/app/server.py`.
- Full server suite: 270 passed, 2 unrelated pre-existing failures remain:
  `test_ui_definitions_are_complete_for_all_item_types` (`journalFolder`
  metadata mismatch) and `test_guarded_house_denial_knocks_outside_and_inside`
  (test client lacks `item.use`).
- Live `chat-grid.service` restarted successfully and is active, MainPID
  `3226340`.
- Public Indiginious web entry remains HTTP 200 and reports release `0.4.13`
  / client revision `R536`.

The web help/docs source now lists the homecoming commands. The client bundle
was not rebuilt or replaced because this feature is server-side and the shared
repository contains unrelated active work.
