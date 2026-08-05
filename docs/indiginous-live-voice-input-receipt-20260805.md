# Indiginous live voice-input receipt

Updated 2026-08-05 from the server workspace.

## Change

- Added a browser speech-input bridge that starts only after the Indiginous
  microphone has been granted and the world session is connected.
- Final recognized speech is sent as a private in-world message to the
  companion when Clawdia/Claudia/Missi is present; otherwise it falls back to
  the room chat path.
- Existing WebRTC microphone capture remains unchanged for peer audio.
- Speech recognition stops with the world session and reports blocked or
  unsupported browser permissions without claiming the mic is working.

## Proof

- Client build: passed with Vite.
- Client tests: 29 passed across 9 files.
- Published client revision: `R546`.
- Public HTML, JavaScript, CSS, version, branding, and help assets: HTTP 200.
- Published JavaScript contains the speech-input bridge markers.
- Public WebSocket `wss://blind.software/indiginous/ws`: HTTP 101.
- `chat-grid.service` and `chat-grid-companion.service`: active.
- Companion state: connected, nickname `Clawdia`, location
  `raywonder_house_bedroom`.
- Recovery copy: `backups/indiginous-before-mic-20260805-004013/`.

## Remaining user-side proof

The browser must still grant speech-recognition permission when prompted. The
server can verify the published path and companion connection, but it cannot
hear the physical microphone from this workspace without a live browser
session using the updated client.
