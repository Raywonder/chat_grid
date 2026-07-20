# Endiginous Windows Desktop

This is the first official Windows desktop shell for Endiginous. It wraps the existing web client in Electron so the audio, WebRTC, sign-in, controls, and item logic stay shared with the browser client.

The app defaults to the live Endiginous at:

```text
https://blind.software/chatgrid/
```

## Development

Install dependencies:

```bash
cd desktop/windows
npm install
```

Open the live grid:

```bash
npm start
```

Open a local Vite client instead:

```bash
npm run start:local
```

To override the URL on Windows PowerShell, use:

```powershell
$env:CHGRID_DESKTOP_URL = "http://localhost:5173/"
npm start
```

## Packaging

Build the Windows installer and portable app from Windows:

```bash
cd desktop/windows
npm install
npm run package:win
```

Artifacts are written to `desktop/windows/release/`.

Packaging runs `npm run build:web` first. That builds the shared web client with
relative asset paths and copies it to `desktop/windows/web/`, including the full
`sounds/` tree for local desktop use and remote fallback packaging.

## Shortcuts

- `Ctrl+Enter`: connect
- `Ctrl+Shift+Enter`: disconnect
- `Ctrl+,`: audio setup
- `Ctrl+G`: focus the grid
- `Ctrl+R`: open in-world reactions and user actions
- `Ctrl+Shift+U`: switch between live and local Endiginous URL
- `Ctrl+Shift+I`: developer tools

## Notes

- The wrapper intentionally reuses the current web app instead of duplicating Endiginous behavior.
- Microphone, media, and speaker-selection permissions are allowed for the app session.
- Package from Windows for real Windows artifacts; Linux can validate the source and lockfile but should not be treated as a Windows runtime proof.
