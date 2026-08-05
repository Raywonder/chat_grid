# Indiginous macOS authentication compatibility receipt — 2026-08-05

## User report and demonstrated causes

- Public macOS 0.4.5/R517 is an Intel-only `x86_64` app and macOS displays the legacy Intel-app warning.
- Its browser flow requests the retired `endiginous_client_auth_start` route, which returned HTTP 404 before repair.
- The current route is `indiginous_client_auth_start`; callback and state validation were already correct.

## Live compatibility repair

- Blind Software now normalizes only `endiginous_auth_start` and
  `endiginous_client_auth_start` to their current Indiginous handlers before
  dispatch.
- Existing callback, state, account, and assertion validation remains unchanged.
- Production backup:
  `/home/blindsoft/public_html/index.php.bak-20260805-1244-endiginous-auth-compat`
- `php -l` passed. A valid-shaped legacy client request now returns HTTP 302 to
  the Blind Software login instead of 404.
- Account download labels now identify the public Mac files honestly as
  Indiginous 0.4.5 for Intel Macs, with file types and approximate sizes.

## Current-source repair

Source commit `3af7673bea471d67f5b0d5232688beda5f402d9a`:

- brings the macOS browser to the foreground instead of opening it with
  `open -g`;
- speaks sign-in failure and retry guidance, then restores focus to the visible
  main window rather than a hidden login-panel button;
- defaults PyInstaller to `universal2`, requiring an explicit override for any
  local Intel-only compatibility build;
- aligns `CFBundleVersion` with 0.4.18;
- adds focused source tests for the browser and architecture contracts.

Verification:

- Server focused tests: 15 passed.
- Exact source was bundled to the approved Intel Mac build lane.
- Mac native test suite: 51 passed, 2 skipped.
- Source preflight: wxPython 0.4.18/R548 passed before the source commit.
- Git commit was pushed to Dominique-owned Gitea and GitHub repositories.

## Release decision

The current public Mac package is not replaced. The reachable Mac is Intel and
its Python 3.14 plus wxPython native libraries are `x86_64` only. PyInstaller's
bootloader is universal, but that cannot turn Intel-only Python/wx libraries
into a valid Apple Silicon app. A signed/notarized arm64 or true universal2
artifact must be built on an appropriate Apple Silicon/universal dependency
lane, then verified with `lipo -archs`, codesign, Gatekeeper, notarization,
fresh VoiceOver sign-in/callback/world entry, public checksum, and updater
metadata before promotion.

Next safe action: build commit `3af7673` on an approved Apple Silicon Mac lane,
run the complete macOS release preflight, and only then replace the stable DMG,
ZIP, checksum, and manifest.
