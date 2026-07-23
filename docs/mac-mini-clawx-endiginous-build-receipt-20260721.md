# Intel Mac mini ClawX and Endiginous build receipt

Date: 2026-07-21
Host: `admin-s-mac-mini.tailnet.raywonderis.me` (`x86_64`, macOS 15.7.7)
Toolchain: Xcode 26.3, Swift 6.2.4, Python 3.14.5

## ClawX

Source: `/Users/admin/git/Raywonder/ClawX`
Revision: `9063011bc124103711da0482c5bc5d2a7a71e5a9`
Build command: `CSC_IDENTITY_AUTO_DISCOVERY=false pnpm package:mac`

- Typecheck passed.
- ESLint check passed without modifying files.
- The full macOS package path completed for x64 and arm64.
- The x64 app launched successfully from `release/mac/ClawX.app`; it was closed after verification.
- Existing release files were preserved in `release/recovery-pre-unsigned-20260721-211258/`.
- The normal signed pass was attempted first but stopped because the Mac keychain has duplicate matching Developer ID certificate names. The successful pass is unsigned/ad-hoc and is for internal verification only.
- The ClawX test suite has 93 passing tests and 4 existing failures in `tests/unit/stores.test.ts` because the Node test environment has no `localStorage.setItem`; this is separate from macOS packaging and remains unresolved.

Artifacts and SHA-256:

- `release/ClawX-0.1.24-mac-x64.dmg` — `01774de873681adb1d08e91179a30c34d9518d69a16108c51c0cbf38f0d30701`
- `release/ClawX-0.1.24-mac-x64.zip` — `1e06da500d9ca10ae021fe219ed4128e2f39e96b8b48865825463f2334d9444b`
- `release/ClawX-0.1.24-mac-arm64.dmg` — `58bd47fce64ad45c91c54269374f46037dd4ff2ca70299db28780fb90bc2b856`
- `release/ClawX-0.1.24-mac-arm64.zip` — `7e70d9b4453aabe13bfa802a96e0ed9194b7861a8b908535937d3252404fcc0b`

## Endiginous

This is a separate build from ClawX; it is not included in the ClawX application.

Source staged on the Mac at: `/Users/admin/git/Raywonder/Endiginous/desktop/native`
Build command: `PYTHON_BIN=python3 ./macos/scripts/build-macos.sh`

- The first test run found one platform-specific updater test hardcoding a Windows `.exe` name. The smallest correction made `tests/test_updater.py` choose `.zip` on macOS and `.exe` on Windows.
- After that correction, all 34 tests passed.
- PyInstaller produced the x86_64 `dist/Endiginous.app`.
- The app launched successfully and was closed after verification.
- The build generated the unsigned internal DMG and ZIP; no public feed or release metadata was changed.

Artifacts and SHA-256:

- `/Users/admin/git/Raywonder/Endiginous/desktop/native/macos/release/Endiginous-0.4.3-macOS.zip` — `5b53e8cbc4319624d18302778c616f90bb5fab41ec54e29770ba30f9a64e1bef`
- `/Users/admin/git/Raywonder/Endiginous/desktop/native/macos/release/Endiginous-0.4.3.dmg` — `74d95d89d03e42dff89c3d58f2a196e0472382a8618adc99b9114523551e7ffe`

Both launched test applications were closed, and no build/test app processes were left running.
