# Desktop dialog and audio settings repair

Date: 2026-07-22

## Changed

- Made the wxPython desktop settings dialog handle OK, Cancel, and Escape explicitly with `EndModal`, fixing dialogs that could remain open after activation.
- Added the same explicit modal lifecycle handling to the Windows wxPython sibling.
- Added native desktop audio controls for output mode, master volume, microphone gain, voice/item/media/world layers, announcements, radio readouts, item beacons, and movement announcements.
- Added a native-to-shared-client bridge so those settings are persisted and applied without duplicating a second audio engine.
- Kept device selection and the complete account/world audio dialog under File > Settings in the embedded client.

## Verification

- Python source compilation passed for both desktop source trees.
- Native focused tests: 13 passed after the regression assertions were added.
- Windows wxPython focused tests: 6 passed.
- Client production build passed with Vite; only the existing chunk-size warning remains.
- Full wx runtime/UI verification is still pending on the Windows/Mac build hosts because this server does not have wxPython or a desktop display.
