# Indiginous R552 retention and release-gate receipt

Date: 2026-08-17

## Source recovery

The nine-file R552 guest-session and voice-input change deployed on the server
was recovered onto the Gitea-derived release branch without modifying either
dirty Windows checkout, the divergent dirty Mac checkout, or the dirty server
deployment checkout. The recovered file content matches the deployed Git blob
IDs. The canonical `AGENT-CONNECTION-CONTRACT.md` and
`scripts/agent_sync_guard.py` were restored from the governed Mac source and
used for the worktree claim.

R552 provides a keyboard-native guest entry limited to public chat. Guest
sessions do not receive direct-message, voice, wallet, or persistent-account
capabilities. Speech recognition follows the mute state, and voice-entered
messages can suppress sender echo.

## Verification

- Client dependency audit: zero known vulnerabilities after upgrading Vitest
  to 4.1.10 and refreshing the lockfile.
- Client tests: 29 passed.
- Client lint: passed.
- Client production build: passed.
- Accessibility source contract: passed for 33 controls and two expanders.
- Full server test suite under WSL: 293 passed.
- Windows wxPython tests during packaging: 37 passed, one platform-specific
  test skipped.
- Windows PyInstaller and Inno Setup 6.7.3 build: passed.
- Installer artifact: `Indiginous_Setup.exe`, 28,822,137 bytes, SHA-256
  `897f404bfa39c8da4ae79352cb37811c9779cade7b8c202a387f93939dce6a4f`.
- Silent rollback to the prior official R549 package and upgrade to the R552
  candidate both exited successfully. All 501 existing profile-file path/hash
  records were identical before and after the candidate upgrade.

## Publication status

The R552 candidate was not published. It is unsigned, and an interactive basic
Windows UI Automation/keyboard smoke has not yet been completed on the isolated
Windows 11 acceptance VM. Manual NVDA/Narrator acceptance remains intentionally
post-initial-release, but the basic automated UIA gate still applies.

The macOS feed remains on its previously published artifact and is not changed
to R552. The available Mac mini is Intel-only for the current Python/wxPython
toolchain, so it cannot prove the required universal2 artifact. A macOS release
still requires a universal2 dependency/build lane, both-architecture `lipo`
proof, Developer ID signing, hardened-runtime and entitlement verification,
notarization and stapling, Gatekeeper launch, VoiceOver/auth smoke, checksums,
and a tested rollback package. The source preflight correctly remains red for
an all-platform R552 release because `latest-macos.json` is not R552; the feed
was not falsified to bypass that gate.

Future shared diagnostics and release evidence should retain separate,
truthful platform gates for Windows, macOS, and iOS/TestFlight.

## Source retention

The reviewed source was committed as `49ffa3261fd4880b3f9b2dac415185e3f339c81b`
and pushed without rewriting history to Gitea branch
`codex/indiginous-pending-release-r552`. The bare repository was added to the
already-authorized `devinecr` safe-directory list. Its object directories were
made group-writable with setgid, matching the `tappedin` group ownership needed
by both Gitea and the governed release identity. `git fsck --full` reported only
dangling objects from prior/rejected object transfers, not corrupt or missing
reachable objects.
