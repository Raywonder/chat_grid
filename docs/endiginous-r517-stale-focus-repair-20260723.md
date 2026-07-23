# Endiginous R517 stale-focus movement repair

Date: 2026-07-23 CDT

## Cause

After world admission, browser and embedded desktop WebView implementations
can retain `document.activeElement` on the now-hidden Connect or focus button.
The shared keyboard guard classified buttons and links as protected UI and
returned before routing world commands to the canvas. Native Tab navigation and
some platform shortcuts could still appear to work, while movement and other
single-key commands were lost.

## Change

The shared keyboard controller now treats an element that is hidden, inside a
`.hidden`/`[hidden]` subtree, or inside an inert subtree as stale focus. It
returns focus to the canvas for world commands in that case. Visible controls
remain protected so settings and normal form interaction are unchanged.

Client candidate revision: `R517`.

## Verification

- Client tests: 25 passed in 6 files.
- Client lint: passed.
- Client production build: passed.
- `git diff --check`: passed.
- Native keyboard/accessibility checks: 4 native tests and 3 wxPython tests
  passed through an isolated `uvx pytest` runner; a real Windows/macOS launch
  test remains required on the target OS.
- Public Endiginous remains on R516; R517 is not published yet.
- Endiginous publication remains sequenced after the next tCast release and
  requires real target-client keyboard proof.
