# Browser cast controls repair

Date: 2026-07-22 CDT

## Change

Updated the existing Endiginous browser cast path so local and remote audio
casts are visible and keyboard/screen-reader reachable. Cast surfaces now use
native media controls for audio and video and include an explicit **Stop cast**
button. Stopping a local cast releases its tracks, clears the peer stream, and
sends the existing world cast-stop signal when the cast was published. Stopping
a remote cast removes only the local receiver surface and its tracks.

The browser now also has a visible **Open settings and audio** control next to
the connection controls. Its existing dialog remains the single home for
microphone, speakers, announcements, beacons, movement, FlexPBX, cast-local,
and notification preferences. The world keyboard handler no longer redirects
Enter/Space events from buttons or media elements back to the canvas.

No new release tree, app, account, or public download was created.

## Verification

- `git diff --check`: passed.
- Vite production build: passed; generated `dist/assets/index-DAeZKOBK.js`
- Vite production build: passed; generated `dist/assets/index-C6FLb50R.js`
  and completed in 2.66 seconds.
- Repository TypeScript check: still fails on pre-existing unrelated errors
  in audio, presence, admin, input, and message-handler modules. The build
  itself completed successfully.

## Release status

This is source-level progress only. The public Endiginous downloads and update
feeds remain unchanged until browser settings/audio reachability, desktop-tree
parity, Windows/NVDA proof, macOS VoiceOver proof, authenticated movement, and
signed/notarized artifact checks are complete.
