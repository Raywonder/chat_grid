# macOS native client

macOS-specific PyInstaller packaging and signed DMG/ZIP/PKG build tooling live
in this tree.
Shared wxPython application code remains in `../src`.

The native SwiftUI setup scaffold is in `IndiginousSetup/`. It is intentionally
separate from the existing wxPython/WebView client: it provides Recommended
and Custom onboarding for Tailscale/Headscale, Indiginous, and per-user
startup. It does not embed enrollment keys, agent runtimes, or private
credentials.

Run `./scripts/build-macos.sh` on the approved Mac build lane. By default it
uses the verified Apple Developer ID Application and Developer ID Installer
identities from that Mac's keychain, without copying any keychain secret into
the repository. Set `SIGN_MACOS=0` only for an explicitly internal unsigned
build. The PKG installs the signed app under
`/Applications/BlindSoftware/Indiginous.app` and includes the complete local
sound tree; the shared client also refills missing published ambience sounds in
the background. Public release still requires notarization, stapling, and
Gatekeeper verification.
