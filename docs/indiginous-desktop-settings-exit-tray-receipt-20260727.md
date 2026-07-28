# Indiginous desktop settings, exit, and tray receipt

Date: 2026-07-27
Target: Windows wxPython desktop client 0.4.12 / R535

Implemented in source:

- Quit checks the verified update manifest first. With no newer update, an unavailable update, or a failed check, the app quits directly; it does not show an install countdown.
- A newer verified installer is still downloaded, checksum-verified, and offered through the existing visible countdown.
- Tray Open restores the existing window and focuses the world. The redundant tray Focus world item was removed.
- The native Settings dialog now contains the desktop audio controls: stereo/mono, master volume, microphone gain, voice/item/media/world layers, announcement modes, item beacons, movement directions, and binaural audio.
- The duplicate embedded desktop settings/audio surface is hidden; Cast remains available from the native File menu and the in-world remote.
- Settings OK explicitly sets the affirmative return code and closes the modal dialog.

Verification:

- Python compilation passed.
- 26 wxPython tests passed.
- `git diff --check` passed for the changed desktop files.

Not yet verified:

- Fresh Windows installer build and Windows NVDA/UAC runtime proof. The owner Windows build node is offline, and the current Linux environment does not have wxPython or Inno Setup. Existing release artifacts were not overwritten.
