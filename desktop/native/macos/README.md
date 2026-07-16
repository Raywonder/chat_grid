# macOS native client

macOS-specific PyInstaller packaging and DMG/ZIP build tooling live in this tree.
Shared wxPython application code remains in `../src`.

Run `./scripts/build-macos.sh`. Unsigned development artifacts are acceptable
for internal verification; public release still requires Developer ID signing,
notarization, stapling, and Gatekeeper verification.
