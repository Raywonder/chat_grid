# Endiginous native macOS setup scaffold

This is the native SwiftUI onboarding surface for configuring a Mac as an
OpenClaw gateway device. It is separate from the existing wxPython/WebView
client and is intended to become the signed installer/onboarding app.

The first scaffold provides:

- Recommended and Custom setup modes.
- Explicit component choices for Tailscale, OpenClaw, gateway registration,
  per-user startup, and the Endiginous client.
- The approved Headscale and token-free OpenClaw installer defaults.
- HTTPS validation and shell-operator rejection before a plan is created.
- Download and execution are modeled as separate operations; the plan never
  passes a shell pipeline to a privileged process.
- VoiceOver-friendly native labels, hints, focusable controls, and status text.

The execution boundary is deliberately staged. The next implementation step
is a signed macOS privileged helper (SMJobBless or the current Apple-supported
replacement) that runs the selected plan, writes a redacted receipt, and
returns step-by-step results. The app must not embed Tailscale auth keys,
OpenClaw tokens, or private gateway credentials.

Build on a Mac with:

```sh
swift build
swift test
```

The Linux workspace cannot provide the final AppKit/SwiftUI build or real
VoiceOver proof; those remain Mac-side verification items.
