# TappedIn Archive Sound Library

The TappedIn web root has reusable public audio under:

- Local path: `/home/tappedin/public_html/wp-content/uploads/Archive/fx/`
- Public URL root: `https://tappedin.fm/wp-content/uploads/Archive/fx/`

Current folders:

- `Ambiance/` - looping or background place sounds for rooms, streets, parks, offices, forests, beaches, and similar world spaces.
- `wooshes/` - transitions, movement accents, UI sweeps, and portal-style effects.
- `other/` - mixed cinematic FX packs and miscellaneous effects.

Chat Grid widgets can use these as full HTTPS URLs in `emitSound` for ambience loops or `useSound` for one-shot item sounds. Example:

```text
https://tappedin.fm/wp-content/uploads/Archive/fx/Ambiance/AMBSubn-Late_spring_afternoo-Elevenlabs.wav
```

When adding filenames that include spaces or punctuation, prefer copying the browser URL or percent-encoding the path before storing it in item params.

