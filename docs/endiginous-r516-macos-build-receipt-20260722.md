# Endiginous R516 macOS build receipt

Date: 2026-07-22
Source: `/Users/admin/git/Raywonder/Endiginous/desktop/native` on the owner Mac mini
Version: 0.4.4
Revision: R516

## Verified

- Native Mac test suite: 36 passed.
- PyInstaller produced a fresh unsigned x86_64 application bundle.
- Launch smoke started the exact 0.4.4 application process and the test process was cleaned up afterward.
- Fresh artifacts were copied to the server staging folder:
  - `Endiginous-0.4.4-macOS.zip`
  - `Endiginous-0.4.4.dmg`

Checksums:

- ZIP: `f5cb2cc81a67f7743d1df297eb00d82ea9af415c3530a4fbb6083cbfcc0a670b`
- DMG: `352d4883f9d89ff2b414499188b6410451568cb6e4f722bab63b08cf30faa3d6`

## Still blocked before release/public update feeds

- Windows build/accessibility proof is not complete. The Windows 11 VM is reachable, but its encrypted build-share setup currently rejects the credential with a PowerShell `New-PSDrive -Credential` username transformation error.
- Mac VoiceOver and authenticated-world movement/audio proof are still outstanding.
- The Mac artifacts are unsigned internal candidates only. Public downloads and update manifests remain unchanged until the Windows artifact and platform accessibility checks are proven.

Build warning retained for follow-up: PyInstaller reported the optional hidden import `wx.lib.pubsub.core.datamsg` as unavailable, although the build completed and the native tests passed.
