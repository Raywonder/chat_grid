# TappedIn Archive Sound Library

The TappedIn web root has reusable public audio under:

- Local path: `/home/tappedin/public_html/wp-content/uploads/Archive/fx/`
- Public URL root: `https://tappedin.fm/wp-content/uploads/Archive/fx/`

Current folders:

- `Ambiance/` - looping or background place sounds for rooms, streets, parks, offices, forests, beaches, and similar world spaces.
- `wooshes/` - transitions, movement accents, UI sweeps, and portal-style effects.
- `other/` - mixed cinematic FX packs and miscellaneous effects.

Before generating new sound, search this archive and the existing project
sounds first. If neither has the right asset, prefer a fresh ElevenLabs sound or
voice generation pass so the cue is tailored to the object, room, or action.
External audio searches, including YouTube, are a fallback path and should only
be used for reference or for audio with rights/licensing that fit the project.

For Chat Grid rooms and locations, check `Ambiance/` before generating new loops. It already has room and office candidates such as:

- `AMBRoom-Basic_Room_Tone_with-Elevenlabs.wav`
- `AMBRoom-Quiet_vintage_hotel_-Elevenlabs.wav`
- `AMBOffc-Seamless_quiet_offic-Elevenlabs.wav`
- `AMBOffc-Quiet_office_at_nigh-Elevenlabs.wav`
- `AMBOffc-Background_studio_am-Elevenlabs.wav`

The server also has a reusable compressed sound pack at
`/home/tappedin/.openclaw/media/voice-notes/steve-game-sounds-20260703/steve-game-sounds-20260703.zip`.
For the clock item, three short cues from that pack were extracted to
`projects/chat_grid/tmp/archive-sound-staging/steve-game-sounds-20260703/`
and published as web-ready Opus files:

- `sounds/clock/archive/chime-hint-soft.ogg` for manual clock use.
- `sounds/clock/archive/bell-clear-single.ogg` for top-of-hour announcements.
- `sounds/clock/archive/bell-alert-gentle.ogg` for clock alarms.

The clock's default ticking emitter remains `sounds/clock.ogg`, because the
archive pack only had short one-shot bell/chime cues and no better loopable
clock bed.

Chat Grid widgets can use these as full HTTPS URLs in `emitSound` for ambience loops or `useSound` for one-shot item sounds. Example:

```text
https://tappedin.fm/wp-content/uploads/Archive/fx/Ambiance/AMBSubn-Late_spring_afternoo-Elevenlabs.wav
```

When adding filenames that include spaces or punctuation, prefer copying the browser URL or percent-encoding the path before storing it in item params.

For any new published loop or one-shot, keep the original/archive source intact
and publish a trimmed, normalized web copy under the relevant project sound
folder. Verify the file decodes and that the deployed URL returns HTTP 200
before wiring it into item or location behavior.
