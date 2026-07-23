# macOS native client

macOS-specific PyInstaller packaging and DMG/ZIP build tooling live in this tree.
Shared wxPython application code remains in `../src`.

The native SwiftUI setup scaffold is in `EndiginousSetup/`. It is intentionally
separate from the existing wxPython/WebView client: it provides Recommended
and Custom onboarding for Tailscale/Headscale, OpenClaw, gateway-device
registration, and per-user startup. It does not embed enrollment keys or run
privileged changes until the signed macOS helper is added.

Run `./scripts/build-macos.sh`. Unsigned development artifacts are acceptable
for internal verification; public release still requires Developer ID signing,
notarization, stapling, and Gatekeeper verification.
