# Indiginous R542 screen-share remote workflow

Date: 2026-08-04

## Change

- Desktop screen-share capture and received cast media no longer create a
  visible overlay or second media-control window.
- Playback remains owned by the carried TV or radio remote, preserving the
  existing keyboard and screen-reader remote-control path.
- The media remote guide adds a `Shared content` entry for each active shared
  screen targeted at that receiver.
- The shared-content guide entry disappears when the cast stops or the caster
  disconnects; ordinary TV/radio guide entries are unchanged.
- The shared client revision is now `R542`.

## Verification

- Client tests: 29 passed
- Client production build: passed
- Client lint: passed
- Server media-guide tests: 2 passed
- Server Python compile check: passed

Windows installer rebuild, NVDA hands-on verification, and public deployment
remain pending until the matching Windows R542 artifact is built and verified.
