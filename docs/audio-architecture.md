# Audio Architecture

## Audio Domains

- Voice: remote WebRTC peer audio.
- Media: radio station streams.
- Item: looping item emit sounds (`emitSound`).
- World: location ambience plus one-shot spatial world events from others (movement/teleport, social reactions, and item-use spatial sounds).
- UI: interface tones, device button presses, and status cues (not layer-controlled). UI action cues prefer generated ElevenLabs one-shot files under `client/public/sounds/actions/`, and tactile device/radio controls use the local pack under `client/public/sounds/device-buttons/`, with tiny synthesized tones kept only as local fallback if an asset cannot load or decode.

## Layer Toggles

Runtime toggles in normal mode:

- `1`: voice
- `2`: item
- `3`: media
- `4`: world
- `5`: cycle TTS announcement mode
- `6`: optional item beacons
- `7`: stereo/mono output
- `8`: local microphone mute
- `9`: voice layer, mirrored for one-handed access to the end of the audio strip

Shifted number-row shortcuts mirror the same audio strip from `Shift+2`
through `Shift+9`, with `Shift+1` reserved for loopback monitor.

Audio-layer toggles persist in local storage key `chatGridAudioLayers`.

## Layer Off Behavior

Layer off prefers unsubscribe/cleanup instead of only muting:

- Voice: remote peer audio graph is detached; resumes by reattaching stored remote streams.
- Media: `RadioStationRuntime.cleanupAll()` and no sync/update processing until re-enabled.
- Item: `ItemEmitRuntime.cleanupAll()` and no sync/update processing until re-enabled.
- World: location ambience fades out and world one-shots are not played while disabled.

## Location Ambience

World locations advertise an `ambienceKey` and `ambienceName` from the server-owned location list. The browser maps those keys to low-volume looping sound files under `client/public/sounds/ambience/` and crossfades when the user enters another location. Each current location/room has its own loop file: Main City, Forest, Town Square, Arcade, Offices, Houses, and the Raywonder entry, living room, studio, kitchen, bedroom, and relaxation room. The arcade loop is longer and slightly louder to keep the tonal bed steady across loop wraps. The relaxation room uses an ocean-style loop and can also hold item/radio media from the relaxation library. When location data arrives, the client starts preloading the ambience loops for every known map/room profile. If an ambience file cannot be fetched or decoded, the browser falls back to the procedural bed for that same ambience key instead of going silent.

The public Town Square Café uses its own low-volume conversation and kitchen-clatter loop. It is a separate interior location so the café bed starts only after a visitor enters and never leaks across the whole Town Square. The World Cup TV corner is spatial world audio/metadata, while the normal café bed remains on the world ambience layer.

Stream-capable widgets can override the built-in bed for their own location by setting `ambienceScope="location"` and an `emitSound` URL. The highest-priority enabled widget in the current location becomes the world ambience loop, useful for admin-added outdoor beds such as mountains, rivers, forests, or section-level room tone. Location ambience widgets are intentionally not also played as single-tile emitters; use `ambienceScope="tile"` for ordinary local emitters.

Fallback sounds are last-resort only. For any map, room, item, UI action, or station cue with a real sound asset, load/decode that asset first and double-check the result before using synthesized tones or procedural replacements. Do not play a fallback tone while the real sample is still pending, because that can produce duplicate sounds or tones at the same time.

## Usability And Missing-Sound Workflow

Treat every usable object, room, transition, social action, and game-like
interaction as an accessibility surface. If a thing can be used, entered,
opened, carried, pressed, switched, heard, followed, announced, or played with,
it should have a clear text/status result and, when audio helps orientation, a
real sound or voice asset.

When a sound is missing, use this order:

1. Check existing project sounds under `client/public/sounds/`.
2. Check the TappedIn Archive FX library, especially `Ambiance/`, `wooshes/`,
   and `other/`.
3. Generate a purpose-built sound or voice asset with ElevenLabs, then trim,
   normalize, loop-test, and save it into the right project sound folder.
4. Search external sources only when the first three paths do not fit. YouTube
   can be a source option for reference or properly licensed/public-domain
   material, but do not publish extracted audio unless rights and attribution
   are appropriate for the use.

New sounds should be verified before they become world behavior: decode with
`ffprobe` or an equivalent tool, test the public URL after deploy, and listen or
capture proof from the user-facing surface when practical.

## Footstep Surfaces

Local footsteps use the current location's `ambienceKey` to choose a matching surface profile, and nearby-user footsteps use that user's reported location id before playing. Remote steps are only audible when the moving user is in the same location as the listener, so a person walking in another room does not leak stale footsteps into the current room. The client reuses the shared numbered footstep sample set with per-environment pools, gain, and playback-rate variation so the surface changes without requiring a separate full sample pack for every room. Current profiles cover pavement, gravel/leaves, gravel path, rubber arcade floor, office carpet, sidewalk/porch gravel, wood entry, living-room rug, studio floor, kitchen tile, bedroom carpet, and soft relaxation room carpet.

## Item Sound Model

- `useSound`: one-shot played on successful `item_use` (`item_use_sound` packet), controlled by the item audio layer.
- Optional nearby item beacons use the item audio layer and are spatial from the item's tile. Distance also shapes the cue pitch: close beacons play higher/brighter, while farther beacons play lower/softer so distance can be heard without waiting for speech.
- Clock announcements use the clock's built-in EL640 speech samples by default. They are item-layer audio, not optional browser TTS, so the spoken clock voice still plays when the announcement mode is set to alert-sounds-only or required-only. If the server ever sends an empty clock sequence, the client falls back to a short action cue.
- Portal and teleport one-shots are preloaded and scheduled with a small start cushion, a short gain ramp, and a capped peak gain so transition audio has headroom on browsers or devices that underrun easily.
- Door-style place transitions: successful door, room, house, cabin, shack, and shed uses resolve to a real generated door-open one-shot. When that use moves the local player to another location, the browser schedules a matching real door-close one-shot shortly after the arrival packet.
- Billboards: enabled billboard items are active announcement sources, controlled by the item audio layer. When the listener is inside `emitRange`, the browser rotates the billboard's announcement/banner/headline text and announces the same text through the status reader. If `voiceAssetUrl` is set, the browser preloads and plays that real MP3/OGG voice asset through the Web Audio spatial sample path, so distance, direction, and listener movement continue to update while the user walks. If the asset is missing or fails to decode, the older synthetic spatial speaker cue and browser speech synthesis path are used as fallback. Distance changes the synthetic cue: close billboards are clearer and drier, while far billboards become more filtered, reverby, and slightly wobbly/distorted like an older speaker.
- `emitSound`: continuous looping spatial source attached to an item runtime, controlled by the item audio layer.
- Social reactions use the same world-layer one-shot path through `social_action.sound`. Each reaction action should point at its matching packaged local asset under `sounds/reactions/` instead of sharing a generic tap/chat cue, so browser and desktop clients can play the correct sound locally and use the same path remotely.
- Radio and household-device controls play local device-button cues for power, tuning, preset, keypad, plastic, and hardware-toggle presses. Station-switch name stingers still play from the radio's spatial tile when the station actually changes.
- Linked audio systems should model physically sensible relationships. A radio
  can own or sync hidden/internal components such as subwoofers, mids, tweeters,
  satellite speakers, and connectors when that matches a real speaker setup.
  Components that would not realistically belong inside or outside that system
  should not be attached, hidden, or separated just because the runtime supports
  grouped media items.

Current defaults:

- `radio_station`: `useSound=none`, `emitSound=none`
- `dice`: `useSound=sounds/roll.ogg`, `emitSound=none`
- `wheel`: `useSound=sounds/spin.ogg`, `emitSound=none`
- `clock`: `useSound=none`, `emitSound=sounds/clock.ogg`, spoken clock sequence under `sounds/clock/el640/`

Wheel spin packets also trigger a client-side item-layer flourish around the
`sounds/spin.ogg` one-shot. The flourish now prefers the generated ElevenLabs
asset `sounds/actions/wheel-flourish.mp3`; a synthesized motor/tick/chime
version remains only as fallback if the asset cannot load or decode.

`emitSound` uses a base gain multiplier of `0.3` before spatial attenuation.

Preset radios can also define `stationSwitchSound` or per-preset `switchSound`. The built-in Chat Grid Radio uses short MP3 stingers under `sounds/radio/station-switch/`; each stinger is a compact static/tuning burst with the station name embedded inside the noise. Station-switch stingers are intentionally subtle, sped up, and played as spatial one-shots from the radio tile instead of as loud global UI sounds.

Radio stream playback always passes through a radio-body EQ after media effects and speaker-role filters: high-pass cleanup, presence shaping, and low-pass bandwidth limiting. While a listener moves around a directional radio, that body EQ shifts between low, mid, and high tone profiles based on distance and whether the listener is in front of the radio cone.

The Raywonder rooms use this same media path for room music. `Studio boombox`
is a normal radio item inside `raywonder_house_studio`, and `Music under the
studio door` is a quiet entry-hall radio source with lower volume/filtering so
someone outside the studio can hear music playing without being inside the room.
Living room, studio, kitchen, bedroom, and entry-hall house radios follow the
universal radio remote's station changes as one house station set when the
remote's `remoteControlLinkedRadios` setting is on. Remote station changes
preserve each radio's own power state: turning one radio off only turns that
radio off, and turning it back on resumes the current synced station. Remote
volume changes are applied as relative per-speaker steps, so a linked sub, low,
mid, high, or corner speaker can keep its own volume balance while staying synced to
the shared station. Radio `mediaVolume` accepts `0..1000`, with values above
`100` acting as a boost for quiet sources or speaker components. If the
remote owner turns linked control off in the remote settings, the remote only
controls the nearest/current room radio. The relaxation room is intentionally
excluded from that station sync so its calm room audio can stay independent.
The relaxation room has an ocean ambience bed plus an `Ocean relaxation radio` with
TappedIn relaxation/birds tracks and a Steve G. Jones meditation preset staged
under `sounds/radio/relaxation/`.

Mounted wall TVs are modeled as `house_object` items with `objectKind="tv"` and
`placement="wall"`. The intended in-world TV provider path is a second
AAAStreamer encoder on the admin account that can randomly stream playable
audio from the approved media folder for any house/location that has a TV. Wire
that external encoder/folder as a validated stream source before seeding live TV
presets. TVs follow the same shared-world power rule as radios: disconnect,
reconnect, user switching, and client audio cleanup are listener-local events
and must not switch the TV off. When a TV is actively playing, radios in the
same linked media group yield to the TV system. Ordinary music radios switch off
so the room does not play two programs at once. Radio items modeled as
speaker/filter components (`syncWithPrimary=true` or a non-primary
`speakerRole`) instead adopt the TV stream, channel label, now-playing metadata,
and playhead marker so the home theater/speaker system stays synchronized with
the TV.

House objects can also emit item-layer loops. The kitchen fridge uses
`sounds/house/fridge_hum_loop.ogg` as a short-range spatial appliance hum, so it
is heard in the kitchen/near the item rather than mixed into every room's
background ambience.

## Spatialization

- Distance attenuation uses hearing radius from game state. Continuous sources
  such as radios and item emitters use a slower far-field rolloff with a quiet
  edge floor, so standing close to one object can still leave other plausible
  nearby room sounds audible instead of cutting them off abruptly.
- User voice and world one-shots, including nearby user footsteps, prefer Web Audio HRTF binaural panning so movement can wrap around the listener with front/back cues.
- Continuous media and item loops add a quiet parallel reflection path as distance increases. Nearby radios/emitters stay mostly dry and clear; farther sources layer soft early/late reflections behind the direct audio, with darker tone and gentler pan so carried sound feels physical without getting too loud.
- Stereo panning follows horizontal offset as the fallback when HRTF panning is unavailable.
- Mono output mode collapses pan to center.

## Stale Stream Mitigation

Radio stream startup appends a cache-busting query token on runtime creation to avoid stale buffered playback after reconnect/layer re-enable.
Forced reconnect syncs actively retry paused or errored shared radio elements, including HLS media-error recovery when available, so an already-subscribed nearby radio does not remain silent after transport reconnect.

## Remote HLS Playback

Remote radio streams, including `.m3u8` live playlists and server-resolved AAAStreamer playback URLs, are routed through the same-origin media proxy before browser playback. Public AAAStreamer-style station pages at `/s/<slug>` are resolved server-side against the station page/API contract first, including direct station pages on non-default AAAStreamer hosts. HLS detection is performed after proxy URL resolution so the tile audio runtime still uses `hls.js` for proxied live playlists and keeps playback inside the spatial media graph.
Enabled radio items with blank `playbackUrl` are resolved before the server sends a room snapshot, so reconnecting or entering a room does not leave the browser trying to play a station page as audio.

The relaxation room ambience uses a short loop excerpt prepared from the archived FX `other` folder's Tibetan bowls meditation track. Keep the source archive intact and only publish trimmed/normalized web loops under `client/public/sounds/ambience/`.

## TappedIn Archive Sounds

Reusable public FX and ambience files live at `https://tappedin.fm/wp-content/uploads/Archive/fx/`. Use full HTTPS Archive URLs in widget `emitSound` for looping ambience or `useSound` for one-shot effects. See `docs/archive-sound-library.md` for the local path, categories, and a verified example URL.
