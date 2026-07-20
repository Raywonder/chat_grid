# Item Schema

## World Item (server-authoritative)

```json
{
  "id": "string",
  "type": "billboard | cabin | clock | dice | ecrypto_bank | ecrypto_wallet | furniture | house | house_alarm | house_keeper | house_object | piano | qr_code | radio_station | room | service_link | shack | shed | wheel | widget",
  "title": "string",
  "x": 0,
  "y": 0,
  "createdBy": "user-id",
  "createdByName": "username",
  "updatedBy": "user-id",
  "updatedByName": "username",
  "createdAt": 1735689600000,
  "updatedAt": 1735689600000,
  "version": 1,
  "capabilities": ["editable", "carryable", "deletable", "usable"],
  "useSound": "sounds/roll.ogg",
  "emitSound": "sounds/clock.ogg",
  "params": {},
  "carrierId": null
}
```

- `useSound`: optional client-played one-shot sound when item `use` succeeds; global item field and not user-editable in V1.
- `emitSound`: optional continuously-looping spatial sound emitted from the item on the grid; global item field and not user-editable in V1.
- `capabilities`, `useSound`, and `emitSound` are derived from global item-type definitions at runtime (not stored per-instance in persisted state).
- `createdBy` / `updatedBy` are stable user IDs.
- `createdByName` / `updatedByName` are display-name snapshots used for inspect/readout text.
- `useCooldownMs`: global per item type (`radio_station=1000`, `house=1000`, `house_alarm=1000`, `house_keeper=1000`, `ecrypto_bank=1000`, `ecrypto_wallet=1000`, `dice=1000`, `wheel=4000`, `clock=1000`, `widget=1000`, `piano=1000`, `service_link=1000`), not per-instance editable.
- `emitRange`: global spatial range default per item type (`radio_station=10`, `house=12`, `house_alarm=14`, `house_keeper=10`, `ecrypto_bank=12`, `ecrypto_wallet=8`, `dice=15`, `wheel=15`, `clock=10`, `widget=15`, `piano=15`, `service_link=12`).
  - `radio_station` can override this per instance via `params.emitRange` (`5..20`).
- `directional`: global directional attenuation flag per item type (`radio_station=true`, others `false`); `widget` can override per instance via `params.directional`.

## Persisted Item State (`server/runtime/items.json`)

```json
{
  "id": "string",
  "type": "billboard | cabin | clock | dice | ecrypto_bank | ecrypto_wallet | furniture | house | house_alarm | house_keeper | house_object | piano | qr_code | radio_station | room | service_link | shack | shed | wheel | widget",
  "title": "string",
  "x": 0,
  "y": 0,
  "createdBy": "user-id",
  "createdByName": "username",
  "updatedBy": "user-id",
  "updatedByName": "username",
  "createdAt": 1735689600000,
  "updatedAt": 1735689600000,
  "version": 1,
  "params": {},
  "carrierId": null
}
```

- Persisted state stores only instance data.
- Global/type-level properties are loaded from server registry in `server/app/item_catalog.py`.
- Per-type use/update validation and message behavior are implemented in per-item modules under `server/app/items/types/*/definition.py`, `validator.py`, and `actions.py`, discovered via plugins in `server/app/items/types/*/plugin.py`.
- Client-side add/edit metadata is consumed from `welcome.uiDefinitions` via `client/src/items/itemRegistry.ts` (no local fallback definitions).
- End-to-end add-item template: `docs/item-type-template.md`.
- Future container, attachment, visibility, and linked-system fields should be
  validated against real-world plausibility. Do not allow arbitrary in/out states
  just because a generic schema can represent them; an item should only be
  inside, outside, attached, hidden, carried, or separated when that state makes
  sense for the item type and the scenario being modeled.
- Future add-item flows should resolve placement from the user's current
  location instead of requiring manual coordinates or returning generic mounting
  errors. For mountable/placed objects such as TVs, signs, speakers, remotes,
  books, and household objects, the server/client flow should offer valid
  targets like surfaces, walls, shelves, counters, tables, or item-specific
  mounts. If no preferred target exists, use a sensible fallback or explain the
  missing target in plain language.
- Controllable media/device items should support an explicit remote pairing
  model. If a TV, radio, or similar device is created and no compatible remote is
  available in the location, creation should be able to bundle a remote and pair
  it with the new device or connected media group.

## Type Params

### `room`

Room items can represent an indoor room or an outdoor space. Their editable
properties include:

- `spaceKind`: `indoor` or `outdoor`.
- `widthSquares` and `depthSquares`: server-validated dimensions from 1 to 41
  Grid squares, using the world's X/Y scale.
- `squareFeet`: optional approximate real-world floor area from 0 to 100,000.

The size values are descriptive metadata for the generated space and are
spoken when the room is inspected or entered. The server remains authoritative
and rejects missing, non-numeric, or unusably large dimensions.

### `radio_station`

```json
{
  "streamUrl": "",
  "playbackUrl": "",
  "enabled": true,
  "stationIndex": 0,
  "stationPresets": [],
  "mediaChannel": "stereo",
  "mediaVolume": 50,
  "mediaEffect": "off",
  "mediaEffectValue": 50,
  "speakerRole": "primary",
  "linkedMediaGroup": "",
  "syncWithPrimary": false,
  "itemVisibility": "shown",
  "stationName": "",
  "nowPlaying": "",
  "facing": 0,
  "emitRange": 10,
  "surfaceId": "",
  "surfaceTitle": ""
}
```

- `streamUrl`: string, empty allowed until configured. Accepts direct audio stream URLs and public AAAStreamer-style station pages at `/s/<slug>`; the server resolves supported station pages to their current playback URL before the browser plays them.
- `playbackUrl`: server-managed resolved playback URL for supported station pages.
- `enabled`: boolean on/off flag.
  - UI behavior: in property menu, `Enter` toggles on/off directly.
- `stationIndex`: preset station knob index. Left/right in properties adjusts it; `Shift+Enter` on a preset radio tunes to the next station. A carried radio remote can tune compatible radios/speakers in the current location with comma/period variants and adjust connected radio volume with Ctrl+Shift+Up/Down or Ctrl+Shift+U/D.
- `stationPresets`: server-managed preset station list for bundled radios.
- `mediaVolume`: integer, range `0-1000`, default `50`. Values above `100` boost quiet sources or individual speaker components.
- `mediaChannel`: one of `stereo | mono | left | right`, default `stereo`.
- `mediaEffect`: one of `reverb | echo | flanger | high_pass | low_pass | off`, default `off`.
- `mediaEffectValue`: number, range `0-100`, precision `0.1`.
- UI visibility: `mediaEffectValue` is shown only when `mediaEffect != off` (`visibleWhen: {"mediaEffect": "!off"}`).
- `speakerRole`: one of `primary | sub | low | mid | high | high_low_bass`, default `primary`.
- `linkedMediaGroup`: optional group name, max 80 chars. Radio items with the same group can behave like linked speaker/filter components. The browser exposes this as a nearby system picker for radios, while the stored value remains the group key.
- `syncWithPrimary`: boolean, default `false`. When enabled on a non-primary item with a `linkedMediaGroup`, the client uses the group's `primary` item as the shared media source so secondary speaker/filter items stay time-synced.
- `itemVisibility`: one of `shown | quiet`, default `shown`. `quiet` items still play and can be edited on their square, but are skipped by ordinary nearby/list/locate discovery.
- `stationSwitchSound`: optional one-shot sound path/URL used when tuning this radio. Preset entries may provide `switchSound` to override it per station.
- `stationName`: server-managed station label derived from ICY metadata when available.
- `nowPlaying`: server-managed stream title derived from ICY metadata when available.
- `facing`: number, range `0-360`, step `1` (used when `directional=true`).
- UI visibility: `facing` is shown only when `directional=true` (`visibleWhen` metadata).
- `emitRange`: integer, range `5-20`, default `10`.
- `surfaceId` / `surfaceTitle`: server-managed placement fields used when a portable radio sits on a furniture surface.

### `house`

```json
{
  "houseName": "My house",
  "ownerName": "",
  "doorState": "unlocked",
  "targetLocation": "",
  "description": "A user-built house.",
  "welcomeMessage": "Welcome home."
}
```

- `houseName`: max 80 chars.
- `ownerName`: optional owner/family name, max 80 chars.
- `doorState`: `unlocked | locked`.
- `targetLocation`: optional Endiginous interior id. Blank houses get a generated
  interior location with connected entry/exit doors and practical starter
  companion items.
- `description`: short spoken description, max 240 chars.
- `welcomeMessage`: spoken when the house is unlocked and used, max 240 chars.

### `house_object`

```json
{
  "objectKind": "mug",
  "placement": "table",
  "ownerName": "",
  "remoteControlLinkedRadios": true,
  "description": "A small household object.",
  "readableText": "",
  "interactionHint": "",
  "enabled": true
}
```

- `objectKind`: everyday object kind. Includes paper items such as `book`, `notebook`, `letter`, `envelope`, and `note`, plus `remote`, `speaker`, `radio`, and `tv`; TVs can be mounted with `placement="wall"`.
- `readableText`: optional content spoken when the object is used, intended for books, notebooks, letters, envelopes, notes, and signs; max 2000 chars.
- `interactionHint`: optional brief spoken clue for non-obvious interactions; max 160 chars.
- `remoteControlLinkedRadios`: boolean, default `true`, visible for `objectKind="remote"`. When true, the radio remote controls compatible connected radios/speakers in the current location, with explicit Raywonder house groups allowed to span rooms. When false, it controls only the nearest/current-location radio.
- Mounted TV objects are the in-world receiver model for the future second-admin-AAAStreamer TV provider. The actual stream source still needs the approved folder and encoder wiring before live TV presets are seeded.
- Active TVs coordinate radios in the same linked media group: ordinary preset/music radios switch off, while radio speaker components without their own presets can sync to the TV stream and playhead.

### `house_alarm`

```json
{
  "alarmName": "House alarm",
  "houseName": "My house",
  "ownerName": "",
  "alarmMode": "entry_guard",
  "armedState": "armed_home",
  "codeMode": "off",
  "guestCode": "",
  "disarmCode": "",
  "duressCode": "",
  "residentCode": "",
  "accessSetupComplete": false,
  "accessMethod": "account",
  "enrolledUsername": "",
  "codeHint": "",
  "authorizedNames": "",
  "entryPrompt": "Please wait while the house checks whether someone can let you in.",
  "alertPrompt": "House alarm. Someone is at the door.",
  "allowPrompt": "Access allowed. Opening the door.",
  "denyPrompt": "Access denied. Please wait outside.",
  "notificationMode": "in_grid",
  "ntfyTopic": "",
  "waNotifyTarget": "",
  "description": "A voice-enabled house security panel."
}
```

- `alarmMode`: `monitor | entry_guard | privacy`.
- `armedState`: `disarmed | armed_home | armed_away | triggered`; friendly aliases include `off`, `home`, `away`, and `siren`.
- `codeMode`: `off | guest | disarm | guest_disarm`; friendly aliases include `none`, `guest_only`, `disarm_only`, `both`, and `all`.
- `guestCode`, `disarmCode`, `duressCode`, `residentCode`: optional in-world keypad codes, 3-16 characters, digits plus `*` and `#` only after removing spaces/hyphens. Non-empty codes must be distinct. These are item params visible to authorized editors, so never use real home-security secrets.
- `accessSetupComplete` starts false and becomes true only after owner/authorized-resident first-use enrollment. `accessMethod` is `account` or `account_keypad`; `enrolledUsername` is the enrolled signed-in Grid account.
- `codeHint`: optional safe hint visitors can hear without revealing the actual code, max 120 chars.
- `authorizedNames`: comma-separated display names treated as already allowed, max 240 chars.
- `entryPrompt`, `alertPrompt`, `allowPrompt`, `denyPrompt`, `description`: voiced/readout text, max 240 chars each.
- `notificationMode`: `in_grid | ntfy | whatsapp | ntfy_whatsapp`. External modes store configuration hints only until the approved ntfy/OpenClaw WhatsApp notification plugins are wired.
- `ntfyTopic` and `waNotifyTarget`: optional non-secret hook labels, max 120 chars each.

### `house_keeper`

```json
{
  "keeperName": "House keeper",
  "houseName": "My house",
  "repairMode": "auto_repair",
  "backgroundChecksEnabled": true,
  "checkIntervalHours": 6,
  "targetKinds": "radio, object",
  "authorizedNames": "",
  "voicePrompt": "I can check house radios and household items when someone asks.",
  "description": "A small helper agent for in-world house repairs.",
  "lastAutoCheckAt": 0,
  "lastAutoCheckSummary": ""
}
```

- `use`: checks the current house room for supported target kinds. In `auto_repair` mode it fixes common in-world radio state issues such as off radios, invalid station indexes, missing or typo-broken stream URLs, and stale typo-broken playback URLs. It can also mark cracked or broken household objects as repaired.
- `secondary use`: performs a wider house sweep for supported targets.
- `backgroundChecksEnabled`: allows scheduled baseline autonomy. On schedule the keeper moves one adjacent in-bounds tile in its current room, checks supported in-world targets, records `lastAutoCheckAt` and `lastAutoCheckSummary`, and applies the same modeled repairs as manual use.
- `checkIntervalHours`: scheduled check interval from 1 to 168 hours.
- `repairMode`: `inspect | auto_repair`.
- `targetKinds`: comma-separated target kinds, currently `radio` and `object`.
- `authorizedNames`: optional comma-separated display names allowed to ask the keeper to act. Blank means any user in the room may ask.
- House keepers repair modeled Endiginous state only. They do not contact outside services, send notifications, touch accounts, or claim to fix real physical devices unless a separate approved integration is added.

### `service_link`

```json
{
  "serviceKind": "service",
  "url": "",
  "targetLocation": "",
  "portalDestinationMode": "random",
  "portalLocationPool": "",
  "doorState": "unlocked",
  "requiredKeyId": "",
  "keyLocationHint": "",
  "portalState": "open",
  "portalOpenSeconds": 0,
  "portalClosedSeconds": 0,
  "softwareAuthor": "",
  "verificationStatus": "unverified",
  "description": "",
  "launchMessage": "",
  "enabled": true
}
```

- `serviceKind`: one of `app | door | game | house | room | service | site | station | tool | portal`.
- `url`: empty, absolute public `http/https` URL, or site-relative path.
- `targetLocation`: optional Endiginous location id or room entered when used.
- `portalDestinationMode`: `random | static`; random portals choose a destination at use time, while static portals always use `targetLocation`.
- `portalLocationPool`: optional comma-separated location ids for random portals. When empty, random portals choose from public map locations.
- `doorState`: `unlocked | locked`; locked doors report their status and do not move the user unless a matching key unlocks them.
- `requiredKeyId`: optional key id required to unlock a locked door.
- `keyLocationHint`: optional spoken hint for where the matching key might be.
- `portalState`: `open | closed`; portal-specific status. Closed portals report closed and do not move the user.
- `portalOpenSeconds`: seconds a cycling portal remains open before closing; `0` disables timed cycling.
- `portalClosedSeconds`: seconds a cycling portal remains closed before opening; `0` disables timed cycling.
- `softwareAuthor`: author, publisher, or project owner credited for catalog-style software entries, max 120 chars.
- `verificationStatus`: one of `unverified | community_verified | author_verified | staff_verified`.
- `description`: short spoken description, max 240 chars.
- `launchMessage`: optional use-action message, max 240 chars.
- `enabled`: boolean on/off flag.

### `billboard`

```json
{
  "enabled": true,
  "billboardMode": "interactive",
  "itemVisibility": "visible",
  "headline": "",
  "body": "",
  "url": "",
  "announcementText": "",
  "voiceName": "",
  "voiceAssetUrl": "",
  "bannerText": "",
  "rotationSeconds": 12,
  "emitRange": 12
}
```

- `billboardMode`: one of `interactive | display_only | audio_only`.
- `itemVisibility`: `visible | hidden`; hidden/audio-only billboards are not rendered or listed as nearby items but may still be heard.
- `headline`: main billboard headline, max 120 chars.
- `body`: short billboard body/promo copy, max 360 chars.
- `url`: optional public `http/https` URL or site-relative path.
- `announcementText`: text intended for spoken voice announcements, max 500 chars.
- `voiceName`: optional voice label such as a creator/agent name, max 80 chars.
- `voiceAssetUrl`: optional real voice MP3/OGG path or URL. `sounds/...` paths are served from the Endiginous static assets; public `http/https` URLs are validated.
- `bannerText`: optional rotating banner lines separated with `|`, max 500 chars.
- `rotationSeconds`: integer seconds between banner lines, range `3-300`.
- `emitRange`: integer hearing range in squares, range `1-20`.

### `dice`

```json
{
  "sides": 6,
  "number": 2
}
```

- `sides`: integer, range `1-100`.
- `number`: integer, range `1-100`.

### `wheel`

```json
{
  "spaces": "yes, no"
}
```

- `spaces`: comma-delimited string of values.
- Server validation:
  - must include at least 1 value
  - max 100 values
  - each value max 80 chars

### `clock`

```json
{
  "timeZone": "America/Detroit",
  "use24Hour": false,
  "topOfHourAnnounce": true,
  "announceIntervalMinutes": 60,
  "alarmEnabled": false,
  "alarmTime": "12:00 AM"
}
```

- `timeZone`: one representative IANA zone per world UTC offset. Includes:
  `America/Anchorage`, `America/Argentina/Buenos_Aires`, `America/Chicago`, `America/Detroit`,
  `America/Halifax`, `America/Indiana/Indianapolis`, `America/Kentucky/Louisville`,
  `America/Los_Angeles`, `America/St_Johns`, `Asia/Bangkok`, `Asia/Dhaka`, `Asia/Dubai`,
  `Asia/Hong_Kong`, `Asia/Kabul`, `Asia/Karachi`, `Asia/Kathmandu`, `Asia/Kolkata`,
  `Asia/Seoul`, `Asia/Singapore`, `Asia/Tehran`, `Asia/Tokyo`, `Asia/Yangon`,
  `Atlantic/Azores`, `Atlantic/South_Georgia`, `Australia/Brisbane`, `Australia/Darwin`,
  `Australia/Eucla`, `Australia/Lord_Howe`, `Europe/Berlin`, `Europe/Helsinki`,
  `Europe/London`, `Europe/Moscow`, `Pacific/Apia`, `Pacific/Auckland`, `Pacific/Chatham`,
  `Pacific/Honolulu`, `Pacific/Kiritimati`, `Pacific/Noumea`, `Pacific/Pago_Pago`, `UTC`.
- `use24Hour`: boolean (or `on/off` in updates), default `false`.
- `topOfHourAnnounce`: boolean (or `on/off` in updates), default `true`.
- `announceIntervalMinutes`: integer `1` through `60`, default `60`. Use `1` for every minute, `60` for hourly.
- `alarmEnabled`: boolean (or `on/off` in updates), default `false`.
- `alarmTime`: default `12:00 AM`; accepts `HH:MM` (24-hour mode) or `H:MM AM/PM` (12-hour mode).
- UI visibility: `alarmTime` is shown only when `alarmEnabled=true` (`visibleWhen` metadata).
- Global defaults: `useSound=none`, `emitSound=sounds/clock.ogg`.
- Manual clock use returns the formatted current time to the activating user. Clock speech announcement audio is also emitted via `item_clock_announce` packets using `/sounds/clock/el640/*.ogg`.

### `widget`

```json
{
  "enabled": true,
  "directional": false,
  "facing": 0,
  "emitRange": 15,
  "emitVolume": 100,
  "emitSoundSpeed": 50,
  "emitSoundTempo": 50,
  "emitInitialDelay": 0,
  "emitLoopDelay": 0,
  "emitEffect": "off",
  "emitEffectValue": 50,
  "ambienceScope": "tile",
  "ambienceName": "",
  "ambiencePriority": 50,
  "useSound": "",
  "emitSound": ""
}
```

- `enabled`: boolean (or `on/off` in updates), default `true`.
- `directional`: boolean (or `on/off` in updates), default `false`.
- `facing`: number, range `0-360`, step `1`.
- UI visibility: `facing` is shown only when `directional=true` (`visibleWhen` metadata).
- `emitRange`: integer, range `1-20`, default `15`.
- `emitVolume`: integer, range `0-100`, default `100`.
- `emitSoundSpeed`: integer, range `0-100`, default `50`; controls emitted sound speed/pitch (`0=0.5x`, `50=1.0x`, `100=2.0x`).
- `emitSoundTempo`: integer, range `0-100`, default `50`; controls emitted sound tempo (`0=0.5x`, `50=1.0x`, `100=2.0x`).
- `emitInitialDelay`: number, range `0-300`, precision `0.1`, default `0`; delay in seconds before emitted audio starts after enable.
- `emitLoopDelay`: number, range `0-300`, precision `0.1`, default `0`; delay in seconds between each emitted playback.
- `emitEffect`: one of `reverb | echo | flanger | high_pass | low_pass | off`, default `off`.
- `emitEffectValue`: number, range `0-100`, precision `0.1`, default `50`.
- `ambienceScope`: `tile | location | off`, default `tile`. `tile` plays as a normal spatial item emitter, `location` promotes the widget's `emitSound` stream into the current location ambience bed, and `off` keeps the ambience role disabled.
- `ambienceName`: optional spoken/display name for location ambience, visible when `ambienceScope=location`.
- `ambiencePriority`: integer `0-100`, default `50`; highest priority wins when multiple enabled widgets in the same location offer location ambience.
- `useSound`: empty, filename (assumed under `sounds/`), or full URL.
- `emitSound`: empty, filename (assumed under `sounds/`), or full URL.

### `piano`

```json
{
  "instrument": "piano",
  "voiceMode": "poly",
  "octave": 0,
  "attack": 3,
  "decay": 55,
  "release": 45,
  "brightness": 68,
  "emitRange": 15
}
```

- `instrument`: one of
  `piano | electric_piano | guitar | organ | bass | violin | synth_lead | brass | nintendo | drum_kit`.
- `voiceMode`: one of `poly | mono`.
- `octave`: integer, range `-2..2` (default `0`; bass defaults to `-1`).
- Selecting a new instrument resets `voiceMode`/`octave`/`attack`/`decay`/`release`/`brightness` to that instrument's defaults.
- `attack`: integer, range `0-100`, default `3`.
- `decay`: integer, range `0-100`, default `55`.
- `release`: integer, range `0-100`, default `45`.
- `brightness`: integer, range `0-100`, default `68`.
- `emitRange`: integer, range `5-20`, default `15`.
- `songId`: server-managed song reference used for piano demo/playback content.
- Recorded/demo song payload is stored in server song registry (`runtime/piano_songs.json`) using compact format:
  - `meta`: shared synth parameters
  - `keys`: keyId dictionary
  - `states`: parameter-state dictionary (for mid-song instrument/param changes)
  - `events`: `[t, keyIndex, midi, on, stateIndex]`

## Packet Shapes

- `item_upsert`:

```json
{
  "type": "item_upsert",
  "item": { "..." : "World Item" }
}
```

- `item_remove`:
- `item_pickup` and `item_drop` accept optional `moveAttached: true` when the
  caller wants attached, surfaced, or linked parts to move with the selected
  item. Without it, pickup is only the selected item.

```json
{
  "type": "item_remove",
  "itemId": "item-id"
}
```

- `item_action_result`:

```json
{
  "type": "item_action_result",
  "ok": true,
  "action": "add | pickup | drop | delete | transfer | use | secondary_use | update",
  "message": "human-readable status",
  "itemId": "optional-item-id"
}
```

- `item_use_sound`:

```json
{
  "type": "item_use_sound",
  "itemId": "item-id",
  "sound": "sounds/roll.ogg",
  "x": 12,
  "y": 8
}
```

- `item_clock_announce`:

```json
{
  "type": "item_clock_announce",
  "itemId": "item-id",
  "sounds": ["/sounds/clock/el640/its.ogg", "/sounds/clock/el640/2.ogg", "/sounds/clock/el640/PM.ogg"],
  "x": 12,
  "y": 8
}
```

- `item_piano_note`:

```json
{
  "type": "item_piano_note",
  "itemId": "item-id",
  "senderId": "user-id",
  "keyId": "KeyA",
  "midi": 60,
  "on": true,
  "instrument": "piano",
  "voiceMode": "poly",
  "octave": 0,
  "attack": 15,
  "decay": 45,
  "release": 35,
  "brightness": 55,
  "x": 12,
  "y": 8,
  "emitRange": 15
}
```
