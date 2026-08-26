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

## Public release verification

- Web client deployed at `https://blind.software/indiginous/`.
- Public `version.js` reports `0.4.22` / `R560`.
- Public macOS feed reports `0.4.22` / `R560`.
- Public macOS DMG returns HTTP 200 and SHA-256
  `e55da24816321ede68895249b4bb6f45947db9ec21c85f1b77e50f786b194023`.
- Public macOS ZIP returns HTTP 200 and SHA-256
  `499a03b7b9dc44aa6db8b1a761911d8df3a45640de92a3cf59dab59e3d3a49cc`.
- The macOS package is the verified unsigned Intel/x86_64 build. The
  universal2 signing lane was not publishable on the available Intel build
  host, so the public feed states the architecture and signing status.
- The site's stable download routes point to the exact stable files named in
  the feeds: `Indiginous_Setup.exe`, `Indiginous.dmg`, and
  `Indiginous-macOS.zip`. The live PHP source passed `php -l`.
- A rollback copy of the previous macOS files and feed was preserved under
  `/home/blindsoft/release-backups/indiginous-before-r560-macos-20260826-052602`.

## Windows release boundary

- The public Windows installer remains the verified `0.4.18` / `R549` build,
  HTTP 200, SHA-256
  `8fd924e3e29b9d9f3f9b1ddb3ac3d90059da17e77744ac3fe0167e1daf311ff8`.
- No matching R560 Windows installer was available to verify. The connected
  Windows execution lane required approval, and the available mounted copy
  was an older R551 artifact. It was deliberately not published or used to
  update the feed.
- Windows should be rebuilt and tested on the owner Windows lane before the
  Windows feed or stable installer is advanced to R560.

## Remaining proof

- A hands-on browser bfcache/tab-visibility test and real assistive-technology
  pass remain outstanding.
- Accessibility-lead review did not return before handoff; no accessibility
  finding is being represented as resolved by that review.

## Follow-up: quiet Shift+Arrow turning

- Shift+Left/Right still updates the listener heading and refreshes the
  surrounding spatial sound field, but no longer emits a turn UI blip or a
  spoken `Turned ...` status message.
- Client tests: 35 passed.
- Client lint: passed.
- Client production build and public web deployment: passed.
- Public `version.js` remains `0.4.22` / `R560` after deployment.
