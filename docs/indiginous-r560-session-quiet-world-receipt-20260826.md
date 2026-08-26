# Indiginous R560 session restore and quiet-world receipt

Date: 2026-08-26

## Change

- Re-check the HttpOnly session cookie when a tab returns from the browser
  back/forward cache or becomes visible again, then reconnect automatically.
- Keep the server's authenticated `last_location_id`, `last_x`, and `last_y`
  resume path intact so a returning account re-enters its saved room and square.
- Keep nearby item names in the visible dashboard and deliberate item commands,
  but remove them from the continuously live canvas summary. A room with many
  items no longer causes item-title narration to change as the player walks.
- Do not auto-use nearby seating while walking; furniture posture changes remain
  explicit item actions.
- Fix arrival narration to read the actual player coordinates instead of an
  undefined local variable.
- Preserve intentional sign-out/disconnect behavior so a user who signs out is
  not silently reconnected by a later tab-visibility event.

## Verification

- Client tests: 35 passed.
- Client lint: passed.
- Client production build: passed.
- Focused server session/message tests: 127 passed.
- `git diff --check`: passed.
- Agent sync guard `check`: passed.
- Client revision: R560 / 0.4.22.

## Remaining proof

- Public deployment and a hands-on browser test of bfcache/tab-visibility
  recovery remain unverified in this source-only checkpoint.
- Accessibility-lead review did not return before handoff; no accessibility
  finding is being represented as resolved by that review.
