# Endiginous R516 movement and desktop authentication receipt

Date: 2026-07-22 CDT

## User-visible changes

- Browser arrow presses now run one movement step immediately and still retain
  the animation-loop movement path for held keys.
- Native desktop arrow keys are caught at the embedded WebView boundary and
  forwarded through the shared movement bridge.
- Native desktop sign-in controls are no longer presented in the main window.
  File owns sign-in, alternate-server sign-in, settings, reconnect, and world
  focus actions.
- When the desktop client is not signed in, it speaks a five-second notice and
  then opens the short-lived secure browser token URL. macOS uses `open -g` so
  the browser handoff does not steal the desktop window; Windows uses a new
  browser tab. Windows continues to use NVDA speech, while macOS uses the
  system `say` command.

## Recovery

Live trees were backed up before publishing under:

`/home/tappedin/.openclaw/workspace/projects/chat_grid/recovery/endiginous-r516-before-movement-auth-20260722-004409/`

## Proof

- Web client lint passed.
- Web client build passed for both `/endiginous/` and `/chatgrid/` base paths.
- Web client tests passed: 25 tests in 6 files.
- Native source/keyboard/menu checks passed: 8 tests.
- Native Python source passed `py_compile` and `git diff --check` passed.
- Public `/endiginous/version.js` reports R516.
- Public `/chatgrid/version.js` reports R516.
- Public `/endiginous/` resolves its R516 JavaScript and CSS assets with HTTP
  200.
- Public `/endiginous/ws` upgrades with HTTP 101 and returns an authentication
  challenge advertising expected client revision R516.

## Remaining verification

The Browser plugin is not available in this session, and Playwright is not
installed locally, so final authenticated arrow interaction was not driven by
an automated browser session. The native runtime itself still needs a real
Mac/Windows launch test to verify the spoken countdown and desktop key path on
the target OS.
