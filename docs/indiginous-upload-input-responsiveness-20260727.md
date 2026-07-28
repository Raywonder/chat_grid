# Indiginous upload input responsiveness receipt

Date: 2026-07-27

## Change

- Ambience upload status is announced at most once every five seconds while
  chunks are being sent, instead of announcing every chunk.
- Focus returns to the Indiginous world canvas when the temporary file picker
  closes.
- The browser yields between upload chunks so keyboard events and world input
  remain responsive during large uploads.

## Verification

- `npm run lint` passed.
- `npm test` passed: 7 test files, 27 tests.
- `npm run build` passed with the existing Vite chunk-size warning.
- Built bundle contains the timed upload status and per-chunk scheduling point.

## Not performed

- No public deployment, installer replacement, or Windows native runtime test
  was performed in this source-fix turn.
- The focused keyboard-controller test path requested during verification does
  not exist in the current tree; the available suite was run instead.
