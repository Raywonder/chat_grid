# Chat Grid macOS 0.3.0 unsigned build status

Date: 2026-07-15

- Source is pushed to Gitea `raywonder/chat_grid`, branch `main`, under `desktop/native/macos`.
- Final packaging commit: `171807a8a940bcebec625910a33ffe6e0c4ced7b`.
- Build host: macOS 15.7.7 x86_64 using Python 3.13.14, wxPython 4.2.5, and PyInstaller 6.21.0.
- Automated tests: 10 passed.
- Bundle identifier: `fm.tappedin.chatgrid`.
- Deep-link scheme: `chatgrid:`.
- Architecture: x86_64.
- Launch smoke test: passed.
- Integrity signature: ad-hoc; `codesign --verify --deep --strict` passed.
- Distribution signing and Apple notarization: intentionally deferred. Gatekeeper rejection is expected until those steps are completed.

Artifacts on the Mac build host:

- `/Users/admin/tmp/chatgrid-native-build/macos/release/ChatGrid-0.3.0-macOS.zip`
  - SHA-256: `19308b44e71e513239c374d649b1514c9b750e85f7e891ced974120404994631`
- `/Users/admin/tmp/chatgrid-native-build/macos/release/ChatGrid-0.3.0.dmg`
  - SHA-256: `15a7f2a5a5d41c25f8d3551a996d1d30c0982bba0f3aff8e2da6d888142b65fa`

Do not publish either artifact to the production automatic-update channel before Developer ID signing and notarization.
