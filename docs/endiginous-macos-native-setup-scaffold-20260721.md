# Endiginous native macOS setup scaffold receipt

Date: 2026-07-21

## Implemented

- Added `desktop/native/macos/EndiginousSetup/`, a native SwiftUI executable
  package separate from the existing wxPython/WebView client.
- Added Recommended and Custom setup modes.
- Added component choices for Tailscale/Headscale, OpenClaw, gateway-device
  registration, per-user startup, and the Endiginous client.
- Reused the approved token-free defaults:
  - Headscale: `https://headscale.tappedin.fm`
  - OpenClaw installer: `https://tappedin.fm/downloads/openclaw/openclaw-join-macos.sh`
- Added HTTPS installer validation and rejection of shell operators in planned
  commands.
- Modeled the OpenClaw installer download separately from its `bash` execution
  arguments so the privileged helper will not receive a shell pipeline.
- Added XCTest coverage for the recommended plan, custom selection, and unsafe
  installer URL rejection.
- Added native VoiceOver labels/hints and status text in the setup UI.

## Security boundary

The app does not contain a Tailscale auth key, OpenClaw token, gateway secret,
or private credential. Tailscale enrollment remains interactive, existing
enrollment is intended to be preserved, and gateway approval remains an
explicit owner-side step.

## Verification

- Source/diff review: passed on the Linux workspace.
- `git diff --check`: passed.
- SwiftUI/AppKit compile and XCTest: pending on the Mac build host; this Linux
  environment cannot provide the macOS SDK.
- Real VoiceOver and administrator-authorization flow: pending on the Mac.
- Signed privileged helper and receipt writer: intentionally not claimed; this
  scaffold stops before executing privileged changes.

## Next implementation stage

On the Mac build host, connect the plan to a signed SMJobBless-style helper (or
the current Apple-supported privileged-helper mechanism), add a redacted local
receipt, then verify the full user path with VoiceOver, keyboard-only control,
existing Tailscale enrollment, interactive Headscale sign-in, OpenClaw node
installation, and gateway approval.
