# Indiginous screen-cast audio privacy repair

Date: 2026-07-28

## Problem

The Windows shell requested `loopback` system audio for screen/window casts.
That could capture Indiginous world audio and send it back into the room,
creating an audio feedback loop for everyone.

## Change

- Windows display-media selection now supplies video only; it never requests
  Windows/system loopback audio.
- The client requests `audio: false` for display capture.
- Any audio tracks returned by a browser or shell are stopped and discarded
  before local playback, WebRTC replacement, or world media-state signaling.
- Local cast preview is muted as defense in depth.

This makes screen/window casts intentionally video-only. External app audio
must not be carried through this screen-cast path because the platform cannot
reliably distinguish it from Indiginous/world audio.

## Verification

- Client tests: 28 passed.
- Client lint: passed.
- Client production build: passed; existing chunk-size warning remains.
- Windows shell tests: 4 passed.
- `main.cjs` source contains no loopback selection and no `systemAudio: 'include'`.

No production publish or installer replacement was performed in this repair.
