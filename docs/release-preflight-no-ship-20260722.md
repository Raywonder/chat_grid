# Endiginous 0.4.4 / R516 release preflight — no-ship receipt

Date: 2026-07-22 CDT

## Decision

Do not replace the existing public downloads or update feeds yet. The release
candidate is not accessibility- or platform-proven across all requested
versions.

## Verified

- Native macOS candidate synced to the Intel Mac mini with a recovery copy.
- Mac native tests: 36 passed.
- Mac build completed for unsigned internal artifacts:
  - `Endiginous-0.4.4.dmg`
  - `Endiginous-0.4.4-macOS.zip`
- Mac artifact SHA-256:
  - DMG: `089d6b089ea598096f5658b3ea5a384a463d15f2fc8e27ff15c46d2106e10b6e`
  - ZIP: `a29e99c758128c1aef869b12da576773527d30f3f8f2332f0ee758bda3038104`
- The launched Mac candidate exposed File-menu entries for sign-in,
  alternate-server sign-in, reconnect, world focus, Settings, and Cast.
- Source whitespace check passed.

## Blocking findings

- Windows wxPython and native trees are behaviorally divergent. The legacy
  wxPython path still lacks the required File-menu sign-in flow and exposes an
  incomplete/circular audio-settings path.
- Browser audio cast can autoplay without a reachable stop/pause/volume
  control.
- Browser users have no reachable web Settings/audio opener.
- Native Windows/NVDA UI Automation proof is still unavailable; the VM build
  share credential is failing and the replacement local transfer ran out of
  temporary space before a build could start.
- macOS VoiceOver process/menu proof and authenticated world movement remain
  incomplete; the Mac VoiceOver connection was not available for scripted
  speech verification.
- The source preflight still rejects both update manifests because they retain
  the old 0.4.3/R514 feed metadata until verified Windows artifacts exist.
- Mac artifacts are unsigned internal builds and must not enter the production
  automatic-update channel without signing/notarization approval.

## Resume point

Keep the existing public downloads and feeds unchanged. Resume by fixing the
browser audio/settings accessibility path, choosing one canonical desktop
release tree or bringing the legacy tree into parity, then build and verify
Windows with NVDA/UIA and macOS with VoiceOver before updating checksums,
manifests, account links, or public download files.
