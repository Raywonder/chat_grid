# Indiginous admin ambience upload

Implemented the admin ambience uploader in the desktop/web client and server path.

## User-facing behavior

- In the Admin menu's Location ambience section, `L` opens a file picker for a looping sound.
- `O` opens a file picker for a one-shot sound.
- The picker has an accessible label and accepts OGG, MP3, WAV, M4A, and FLAC files.
- Upload progress is announced through the existing live status region, including start, percentage, completion, cancellation, interruption, and failure.
- Sound details identify whether a catalog entry is a loop or one-shot.
- One-shot sounds cannot be assigned as location ambience loops.

## Server behavior

- Uploads require `server.manage_settings`.
- Uploads are streamed in ordered base64 chunks, supporting the requested 1 GB capacity floor and files up to 5 GB, checksum-verified, and stored under `client/public/sounds/ambience/uploads`.
- Successful uploads are added to `server/config/ambience_catalog.json` with their `kind` preserved.
- The client requests a fresh catalog after completion; the server does not send a duplicate catalog response.

## Verification

- `npx vitest run src/input/adminController.test.ts`: 4 passed.
- `npm run build`: passed; Vite emitted the production client bundle.
- `python3 -m compileall -q server/app`: passed.
- Server focused suite: 114 passed, 1 unrelated guarded-house test deselected.
- `git diff --check` on the changed implementation files: passed.

The desktop installers and live production deployment were not replaced in this pass. Physical NVDA/VoiceOver interaction remains a separate user-device verification step.
