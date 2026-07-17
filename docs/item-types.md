# Item Types

This is behavior-focused documentation for item types and their defaults.

## Shared Item Behavior

- Items are server-authoritative.
- Item placement, visibility, containment, attachment, and carry/drop rules should
  follow real-world plausibility. If an object would not sensibly be inside,
  outside, hidden in, attached to, carried from, or separated from another object
  in a real scenario, Chat Grid should not model it that way. Examples: internal
  speaker components can be hidden/attached as part of one radio system, but a
  freestanding billboard should not be treated as being inside a pocket-like
  object; room fixtures should stay in their room unless a feature explicitly
  defines how they move.
- Built-in service/station items are seeded by the server on startup when missing.
  Existing matching items with the same type, title, and location are preserved.
  Newly shipped built-ins are also checked before authenticated welcomes, so
  restarted or freshly updated servers expose new items to reconnecting users.
- Global per-type fields are injected by the server and are not persisted per-instance:
  - `capabilities`
  - `useSound`
  - `emitSound`
  - `useCooldownMs` (from item catalog)
  - `emitRange` (spatial range in squares)
  - `directional` (directional attenuation enabled)
- Instance fields are persisted in `server/runtime/items.json`.
- Read-only inspect fields include `createdBy` and `updatedBy` for ownership/change tracking.
- Guest access should use the same default limitations the grid applies to anonymous
  or not-logged-in users, while still allowing the full audio experience. Guests
  may visit only public/community-approved locations, use public-safe items, and
  relax where a location explicitly allows it. Guests should not take items,
  alter private spaces, bypass locked/private doors, or enter non-public rooms
  unless the community/location policy allows it.
- Relaxation fixtures such as beds, benches, chairs, couches, stools, and table
  seats should behave like real furniture. Each item needs a realistic capacity,
  posture support (`sit`, `lie`, or both), occupancy tracking, and location/device
  limits. A bench can seat several people; a normal chair seats one; a bed can
  be sat on and lied on only up to its intended size. These fixtures should not
  be carryable unless the specific real-world item would sensibly be movable.
- Using a bed cycles through the natural posture states: sit on the bed, lie
  down on the bed, then get up. A bed represented as a `house_object` with
  `objectKind=bed` follows the same posture rule as a dedicated `furniture` bed.
- Room/location dimensions do not need to be uniform across every map. Size each
  room to fit its real contents, required walking paths, and enough grid space to
  move around those contents. Avoid oversized empty rooms unless more items or
  navigation clearance require that space.
- Simple place markers such as rooms, cabins, shacks, and sheds should use
  `targetLocation` when they represent an enterable interior. Using the item must
  move the user through the normal server-owned `location_changed` flow so the
  user is visibly inside the destination and can navigate there, not only hear an
  "entered" status line.

## `radio_station`

### Defaults
- Title: `radio`
- Params:
  - `streamUrl=""`
  - `playbackUrl=""` (server-managed)
  - `enabled=true`
  - `stationIndex=0`
  - `stationPresets=[]` (server-managed preset list for bundled radios)
  - `mediaChannel="stereo"`
  - `mediaVolume=50`
  - `mediaEffect="off"`
  - `mediaEffectValue=50`
  - `speakerRole="primary"`
  - `linkedMediaGroup=""`
  - `syncWithPrimary=false`
  - `itemVisibility="shown"`
  - `stationName=""` (server-managed, read-only)
  - `nowPlaying=""` (server-managed, read-only)
  - `facing=0`
  - `emitRange=10`
  - `surfaceId=""`
  - `surfaceTitle=""`
- Global:
  - `useSound=none`
  - `emitSound=none`
  - `useCooldownMs=1000`
  - `emitRange=10`
  - `directional=true`

### Use
- `use` toggles `enabled` on/off and broadcasts chat status. Browsers play a short power-switch cue when radio state changes.
- `secondary use` tunes to the next preset station when presets exist. Browsers play a station-name static stinger when configured, falling back to a synthesized station-change sweep, and crossfade the old station out while the new station comes in.
- A carried radio remote can tune connected house radios with comma/period, Ctrl+comma/period, or Ctrl+Shift+comma/period, and can raise/lower connected radio volume with Ctrl+Shift+Up/Down or Ctrl+Shift+U/D. The server only accepts these controls when the remote is actually carried by the user. Remote tuning preserves each radio's own `enabled` state, so an off radio stays off while still receiving the current station index for when it is turned back on. Remote volume changes are relative per speaker, so separate sub/low/mid/high balances stay separate instead of being flattened to one value.
- Disconnecting, switching users, or reconnecting never toggles radio power. Client cleanup stops only that listener's local playback graph; the shared radio stays on until a user explicitly switches it off.
- When no presets exist, `secondary use` reports now-playing metadata (`Playing <song> from <station>`), or `<title> is off` when disabled.
- A room with a radio may also have a remote in that room, but the remote is
  optional. A radio system can auto-link room speakers by `linkedMediaGroup`,
  including sub, low, mid, high, and satellite/corner speaker components. A
  bedroom or media room can model a surround setup with speakers mounted on the
  walls or in the room corners while keeping active speakers synchronized to the
  same station and station-change state. Each speaker keeps its own
  `mediaVolume`, so users can balance a sub, mid, high, or corner speaker
  separately.
- Shelves, counters, tables, and other furniture surfaces can hold multiple
  radio/speaker components up to their `surfaceSlots` capacity, so a user can
  build a matched shelf set such as low, mid, high, and sub speakers when the
  surface has enough slots.
- The browser presents `linkedMediaGroup` as a nearby linked-system picker for
  radios instead of requiring people to type group keys by hand. Selecting a
  listed radio/speaker system writes that system's group value internally.
- A blank non-primary speaker component (`sub`, `low`, `mid`, `high`, or
  `high_low_bass`) dropped or edited near an active grouped radio automatically
  adopts that nearby playing group's link and syncs with its primary source.

### Validation
- `mediaChannel`: `stereo | mono | left | right`
- `stationIndex`: preset station knob index. With presets, the index wraps around the available station list.
- `mediaVolume`: integer `0..1000`; values above `100` boost quiet sources or speaker components.
- `mediaEffect`: `reverb | echo | flanger | high_pass | low_pass | off`
- `mediaEffectValue`: number `0..100` with `0.1` precision
  - Visible only when `mediaEffect != off` (`visibleWhen: {"mediaEffect": "!off"}`)
- `speakerRole`: `primary | sub | low | mid | high | satellite | high_low_bass`
- `linkedMediaGroup`: optional shared group name, max 80 chars. In the browser,
  choose a nearby linked radio/speaker system from the list instead of typing
  this key manually.
- `syncWithPrimary`: boolean or on/off style input. When enabled on a non-primary grouped radio, the browser uses the group's primary item as the shared playback source so linked speaker/filter items stay synced.
- `itemVisibility`: `shown | quiet`. Quiet items continue to play and remain editable on their square, but are omitted from normal nearby, list, and locate discovery.
- `stationSwitchSound`: optional media path/URL for the station-change stinger. Built-in station presets use ElevenLabs-generated static IDs in `sounds/radio/station-switch/`.
- `facing`: number `0..360` with step `1`
- `emitRange`: integer `5..20`
- `surfaceId` / `surfaceTitle`: server-managed furniture placement fields when a portable radio is sitting on a shelf, table, counter, or other supported surface.
- `stationName` / `nowPlaying`: server-fetched metadata fields; not editable by clients.
- `stationPresets`: server-managed preset station list with title, stream URL, and optional `switchSound` entries.
- `playbackUrl`: server-resolved playback URL for supported station pages; not editable by clients.

## `ecrypto_bank`

### Defaults
- Title: `eCrypto bank`
- Params:
  - `bankName="Crypto eCrypto Bank"`
  - `enabled=true`
  - `serviceScope="wallets_transfers"`
  - `url=""`
  - `description="A town service point for user eCrypto activity."`
  - `accessNote="Use this bank for wallet, balance, transfer, deposit, withdrawal, and eCrypto account tasks when those services are connected."`
- Global:
  - `useSound=none`
  - `emitSound=none`
  - `useCooldownMs=1000`
  - `emitRange=12`
  - `directional=false`

### Use
- Bank items are fixed service counters. They are intentionally not carryable;
  users navigate to bank branches on the map the same way they navigate to other
  places and items.
- Logged-in users are auto-linked to an eCrypto account by their Chat Grid user id.
- `use` reports the current user's linked eCrypto status, including internal
  test-chain `TEST-ECR` balance and connected wallet counts.
- `secondary use` reports bank details and command help.
- `/ecrypto balance` reports the current logged-in user's account status.
- `/ecrypto wallets` lists connected test and real-chain wallet records.
- `/ecrypto connect <test|real> <chain> <address> [label]` links a wallet record
  to the current user's eCrypto account. Real-chain links are stored for account
  use, but Chat Grid does not send real-chain transactions until an approved
  provider/signature flow is wired.
- `/ecrypto faucet [amount]` credits internal test-chain `TEST-ECR` for grid
  testing.
- `/ecrypto transfer <username> <amount> [memo]` transfers internal test-chain
  `TEST-ECR` between Chat Grid accounts.

### Validation
- `serviceScope`: `wallets | wallets_transfers | deposits_withdrawals | full_service | information_only`
- `bankName`: max 120 chars, falls back to `Crypto eCrypto Bank`
- `url`: optional validated media/public URL reference, max 2048 chars
- `description`: max 360 chars
- `accessNote`: max 500 chars
- Wallet command `network_mode` must be `test` or `real`; chain identifiers are
  lowercase alphanumeric tokens with `.`, `_`, `:`, or `-`; addresses may not
  contain spaces.

### Built-in branches
- Built-in branches are seeded in Main City, Town, Forest, Offices, Arcade, and
  Houses at different coordinates so they can be found and navigated to as
  stationary places on the map.

## `ecrypto_wallet`

### Defaults
- Title: `eCrypto wallet`
- Params:
  - `walletName="Pocket eCrypto wallet"`
  - `networkMode="test"`
  - `chain="ecrypto-test"`
  - `address=""`
  - `walletLabel=""`
  - `custodyMode="carried"`
  - `description="A portable wallet marker you can carry on the grid."`
  - `enabled=true`
- Global:
  - `useSound=none`
  - `emitSound=none`
  - `useCooldownMs=1000`
  - `emitRange=8`
  - `directional=false`

### Use
- Wallet items are portable crypto wallet markers. Users can pick them up,
  carry them, drop them, inspect them, and use them as in-world wallet objects.
- `use` reports the wallet mode, chain, optional label/address, and reminds the
  user to visit an eCrypto bank branch or use `/ecrypto` for account actions.
- The seeded Town starter wallet is a test-chain carryable wallet marker.

### Validation
- `networkMode`: `test | real`
- `custodyMode`: `carried | account_link | cold_storage | watch_only`
- `walletName`: max 120 chars
- `chain`: lowercase alphanumeric chain identifier with `.`, `_`, `:`, or `-`
- `address`: max 240 chars and may not contain spaces
- `walletLabel`: max 120 chars
- `description`: max 360 chars

## `house`

### Defaults
- Title: `house`
- Params:
  - `houseName="My house"`
  - `ownerName=""`
  - `doorState="unlocked"`
  - `requiredKeyId=""`
  - `keyLocationHint=""`
  - `description="A user-built house."`
  - `welcomeMessage="Welcome home."`
- Global:
  - `useSound=sounds/teleport_start.ogg`
  - `emitSound=none`
  - `useCooldownMs=1000`
  - `emitRange=12`
  - `directional=false`

### Use
- `use` opens an unlocked house and speaks the welcome/owner/description text.
- Locked houses report that the house is locked. When `requiredKeyId` is set,
  the server can unlock the door if the visitor carries a matching key item or
  a matching key is sitting on the door square.
- `secondary use` speaks house details without opening it.

### Validation
- `houseName`: max 80 chars, defaults to `My house` when blank
- `ownerName`: max 80 chars
- `doorState`: `unlocked | locked`; accepts friendly aliases such as `public/private`
- `requiredKeyId`: optional key id required to unlock a locked house
- `keyLocationHint`: optional spoken hint for where the matching key might be
- `description`: max 240 chars
- `welcomeMessage`: max 240 chars

## `house_alarm`

### Defaults
- Title: `alarm panel`
- Params:
  - `alarmName="House alarm"`
  - `houseName="My house"`
  - `ownerName=""`
  - `alarmMode="entry_guard"`
  - `armedState="armed_home"`
  - `codeMode="off"`
  - `guestCode=""`
  - `disarmCode=""`
  - `duressCode=""`
  - `codeHint=""`
  - `authorizedNames=""`
  - `entryPrompt="Please wait while the house checks whether someone can let you in."`
  - `alertPrompt="House alarm. Someone is at the door."`
  - `allowPrompt="Access allowed. Opening the door."`
  - `denyPrompt="Access denied. Please wait outside."`
  - `notificationMode="in_grid"`
  - `ntfyTopic=""`
  - `waNotifyTarget=""`
  - `description="A voice-enabled house security panel."`
- Global:
  - `useSound=sounds/notify.ogg`
  - `emitSound=none`
  - `useCooldownMs=1000`
  - `emitRange=14`
  - `directional=false`

### Use
- `use` on a disarmed alarm reports that the house alarm is disarmed.
- `use` by an authorized display name speaks the allow prompt and does not trigger.
- `use` with a matching in-world guest code speaks the allow prompt and does not trigger.
- `use` with a matching in-world disarm code marks the panel `disarmed`.
- `use` with a matching in-world duress code appears accepted to the visitor while still broadcasting an alert and marking the panel `triggered`.
- `use` by any other visitor speaks the entry prompt, broadcasts the alert prompt to nearby listeners with visitor/location context, and marks the panel `triggered`.
- `secondary use` speaks alarm mode, armed state, code status, notification hook status, owner, safe code hint, and description without triggering the alarm. It does not speak actual code values.
- Real-world ntfy/WhatsApp sends are not performed by the item itself yet. `notificationMode`, `ntfyTopic`, and `waNotifyTarget` are configuration hooks for the future approved notification plugins.
- Exterior house doors may link to a panel through `accessAlarmItemId`. The server keeps unauthorized users outside, while a recognized resident or successful keypad entry receives a short-lived, single-use entry grant.
- The accessible keypad masks code characters from speech and submits the credential separately from the visitor's display name, so invalid codes are never broadcast as names.

### Validation
- `alarmName`, `houseName`, `ownerName`: max 80 chars; blank names fall back to useful defaults
- `alarmMode`: `monitor | entry_guard | privacy`
- `armedState`: `disarmed | armed_home | armed_away | triggered`; aliases include `off`, `home`, `away`, `alarm`, and `siren`
- `codeMode`: `off | guest | disarm | guest_disarm`; aliases include `none`, `guest_only`, `disarm_only`, `both`, and `all`
- `guestCode`, `disarmCode`, `duressCode`: optional in-world keypad codes, 3-16 characters, digits plus `*` and `#` only after removing spaces/hyphens. Non-empty codes must be distinct. Do not use real home-security secrets.
- `codeHint`: optional safe hint, max 120 chars
- `authorizedNames`: comma-separated display names, max 240 chars
- `entryPrompt`, `alertPrompt`, `allowPrompt`, `denyPrompt`, `description`: max 240 chars
- `notificationMode`: `in_grid | ntfy | whatsapp | ntfy_whatsapp`; aliases include `wa`, `ntfy wa`, and `local`
- `ntfyTopic`, `waNotifyTarget`: optional non-secret hook labels, max 120 chars

## `house_keeper`

### Defaults
- Title: `house keeper`
- Params:
  - `keeperName="House keeper"`
  - `houseName="My house"`
  - `repairMode="auto_repair"`
  - `backgroundChecksEnabled=true`
  - `checkIntervalHours=6`
  - `targetKinds="radio, object"`
  - `authorizedNames=""`
  - `voicePrompt="I can check house radios and household items when someone asks."`
  - `description="A small helper agent for in-world house repairs."`
  - `lastAutoCheckAt=0`
  - `lastAutoCheckSummary=""`
- Global:
  - `useSound=sounds/actions/ui-confirm.mp3`
  - `emitSound=none`
  - `useCooldownMs=1000`
  - `emitRange=10`
  - `directional=false`

### Use
- `use` checks the current room for supported in-world repair targets.
- `secondary use` sweeps the wider house.
- When background checks are enabled, the server gives the keeper baseline autonomy:
  on its schedule it moves one adjacent in-bounds tile in its current room, checks
  supported in-world targets there, records `lastAutoCheckAt` and
  `lastAutoCheckSummary`, and applies the same modeled repairs as manual use.
- In `auto_repair` mode, supported radio repairs include powering a room radio back on, normalizing a bad preset index, restoring a missing or typo-broken `streamUrl` from presets, and clearing stale typo-broken `playbackUrl` values so the server can resolve playback again.
- Supported household-object repairs currently mark `broken` or `cracked` modeled objects as `repaired`.
- In `inspect` mode, the keeper reports what it checked without changing item state.
- House keepers do not silently contact outside services, send messages, touch accounts, or claim to fix real physical devices.

### Validation
- `keeperName`, `houseName`: max 80 chars; blank names fall back to useful defaults
- `repairMode`: `inspect | auto_repair`
- `backgroundChecksEnabled`: boolean-like value for scheduled in-world checks
- `checkIntervalHours`: integer from 1 to 168
- `targetKinds`: comma-separated target kind list, max 160 chars
- `authorizedNames`: optional comma-separated display names, max 240 chars. Blank means any user in the room may ask.
- `voicePrompt`, `description`: max 240 chars
- `lastAutoCheckAt`: server-managed Unix millisecond timestamp
- `lastAutoCheckSummary`: server-managed summary, max 240 chars

## `service_link`

### Defaults
- Title: `service`
- Params:
  - `serviceKind="service"`
  - `url=""`
  - `targetLocation=""`
  - `doorState="unlocked"`
  - `requiredKeyId=""`
  - `keyLocationHint=""`
  - `portalState="open"`
  - `portalOpenSeconds=0`
  - `portalClosedSeconds=0`
  - `softwareAuthor=""`
  - `verificationStatus="unverified"`
  - `description=""`
  - `launchMessage=""`
  - `enabled=true`
- Global:
  - `useSound=none`
  - `emitSound=none`
  - `useCooldownMs=1000`
  - `emitRange=12`
  - `directional=false`

### Use
- `use` speaks the launch message when configured, otherwise it speaks the service/app details, software author, verification status, and URL.
- When `targetLocation` is set, `use` enters that location unless `doorState="locked"`.
  Locked doors with `requiredKeyId` can be unlocked by a matching key object
  carried by the visitor or sitting on that door's square; otherwise the locked
  message may include `keyLocationHint`.
- Portal links use portal-specific open/closed language. A portal with
  `portalState="closed"` reports that it is closed and does not move the user.
  When both `portalOpenSeconds` and `portalClosedSeconds` are greater than `0`,
  the server alternates the effective state from the item's last update time:
  open for the open duration, then closed for the closed duration, repeating.
  Portals use `portalDestinationMode="random"` by default and choose a public
  map destination at use time. Set `portalDestinationMode="static"` to make the
  portal always enter `targetLocation`; set `portalLocationPool` to a
  comma-separated list when a random portal should choose only from specific
  locations.
- Game links with a URL broadcast a grid-positioned `item_game_launch`; other clients only auto-open the game when they are standing on that same item square.
- `secondary use` always speaks the full service/app details, including door status when the item enters a location.

### Validation
- `serviceKind`: `app | door | game | house | room | service | site | station | tool | portal`
- `url`: empty, absolute public `http/https` URL, or site-relative path
- `targetLocation`: optional Chat Grid location id or room entered when the service is used
- `portalDestinationMode`: `random | static`
- `portalLocationPool`: optional comma-separated location ids
- `doorState`: `unlocked | locked`
- `requiredKeyId`: optional key id required to unlock a locked door
- `keyLocationHint`: optional spoken hint for where the matching key might be
- `portalState`: `open | closed`
- `portalOpenSeconds`: number `0..86400`
- `portalClosedSeconds`: number `0..86400`
- `softwareAuthor`: max 120 chars
- `verificationStatus`: `unverified | community_verified | author_verified | staff_verified`
- `description`: max 240 chars
- `launchMessage`: max 240 chars
- `enabled`: boolean or on/off style input

### Built-In Seeds
- City: `Chat Grid Radio` with SoulFoodRadio, DivineCreations radio, Chris Mix Radio, StreamMadness, VoiceLink-popular streams, and ACB Media 1 through 10 as knob presets, plus `AAAStreamer`, `blind.software`, `tappedin.fm`, and portals to Town, Arcade, Offices, and Houses
- Town: `tCast`, `Bema Media Player`, `Thrive Messenger`, and a return portal to Main City

### BlindSoftware Catalog Placement
- Software catalog entries should credit the software author or publisher in `softwareAuthor`; verification status is a trust marker, not a substitute for attribution.
- Public-safe software can be discoverable spatially through grid locations, forums/squares, portals, and billboards. A town-square billboard may rotate a showcase of software entries, while forum-style areas may let guests and members browse nearby software through normal item interaction.
- Town Square has a public café interior with accessible clear approaches, two tables, four usable chairs, a service counter, a spatial café ambience bed, a wall-mounted World Cup TV, and an adjacent accessible live-score billboard. The score board refreshes from FIFA's official public match-calendar JSON feed and links to FIFA's schedule/results page. No match video or commentary audio is restreamed by Chat Grid; broadcaster rights and regional availability remain external.

### FIFA live-score provider dependency

- Provider: FIFA public match calendar (`api.fifa.com`) and official schedule/results page (`www.fifa.com`).
- Purpose: current World Cup teams, score, status, and match clock for the Town Square Café board/TV metadata.
- Authentication/secrets: none.
- Cost: none known for the public endpoint.
- Refresh: every 30 seconds; the last good in-world text remains if FIFA is temporarily unavailable.
- Viewing: the board links to FIFA's official schedule/results and where-to-watch information; Chat Grid does not rebroadcast protected match media.
- Signed-in users can monitor content they own from the owned-content overview, which lists their items and grid coordinates without granting broader admin powers.
- Arcade: `Moonstep Runner`, `Future games shelf`, `Clawdia's toolkit`, and a return portal to Main City
- Offices: `VoiceLink`, `OpenLink`, `OpenClaw and Clawdia`, `FlexPBX`, and a return portal to Main City
- Houses: `Raywonder House front door`, Matthew's nearby accessible home, a return portal to Main City, and connected interior rooms. Exterior alarms and keypads live outside beside the guarded door. The Raywonder studio door is private by default: using it from the entry hall knocks, and someone inside the studio can use `/allow name` to let that person in for a short time. The bedroom door is locked with a matching bedroom key seeded on the door square so the door can actually be unlocked. Raywonder radios use the shared station preset list by default, so new online streamable stations added to the common radio presets become available to the living room, studio, kitchen, bedroom, relaxation room, and studio-door bleed radios. Matthew's home has its own owner-scoped alarm, living room, music room, playable piano, seating, and independently controllable radios. Rooms with radios may include remotes, but remotes are optional.

## `furniture`

### Defaults
- Title: `table`
- Params:
  - `furnitureKind="table"`
  - `material="wood"`
  - `style="warm home"`
  - `condition="good"`
  - `supportsObjects=true`
  - `surfaceSlots=4`
  - `seatingCapacity=0`
  - `postureMode="none"`
  - `surfaceNote="A steady surface for everyday things."`

### Use
- `use` inspects the surface, or sits/lies/leans when posture support is enabled.
- Beds should support both sitting and lying when the bed is meant to be usable.
  Bed occupancy should respect the physical bed size instead of allowing unlimited
  users.
- A carried `house_object` or portable `radio_station` can be placed on furniture that supports objects.
- Pressing Drop with a carried placeable item automatically places it on the focused open furniture surface, or the first open surface on the current square. Manual object interaction still works as a fallback.
- Dropping a portable radio onto an open shelf, or dropping an open shelf onto a loose radio, resolves to the same physical relationship: the radio sits on the shelf.
- Normal pickup moves only the selected item. Attached/group pickup moves the selected item plus attached, surfaced, or linked parts, so a shelf can move with the radio sitting on it or a room can move with its door and included objects when the user chooses to move the whole attached set.
- `surfaceSlots` is the capacity limit for placed objects and portable radios. A surface with `0` slots has no item space; the default table has `4`, and shelf items can use multiple slots to model top-to-bottom shelf space.

### Validation
- `furnitureKind`: `table | chair | couch | desk | shelf | counter | cabinet | bed | nightstand | plant_stand | rug`
- `material`: `wood | glass | metal | stone | fabric | plastic | mixed`
- `condition`: `new | good | worn | damaged | broken`
- `supportsObjects`: boolean/on-off style value.
- `surfaceSlots`: integer `0..20`.
- `postureMode`: `none | sit | lie | sit_lie | lean`.
- `seatingCapacity`: integer `0..6`.
- `style` and `surfaceNote` are bounded text fields.

## `house_object`

- `objectKind` includes everyday objects plus `remote`, `speaker`, `radio`, and `tv`.
- TV objects follow the same shared-media power rule as radios: disconnecting, switching users, or reconnecting must not turn a TV off. Only an explicit user action should change the TV object's `enabled` state.
- Video-capable TV sources expose a visible native-controls screen while program audio stays spatial and synchronized. Audio-described MP3 programs remain audio-first and do not create a blank video panel.
- TV objects can be mounted with `placement="wall"` and are reserved for the in-world TV provider flow: a second admin AAAStreamer encoder can expose random playable audio from the approved folder as a validated stream source for rooms/houses that contain a TV.
- Radio remotes expose `remoteControlLinkedRadios`. When true, the remote tunes/adjusts the connected house radio set. When false, it controls only the nearest/current room radio.
- TV remotes expose `remoteControlLinkedTvs`. When true, remote channel and volume controls apply to the connected house TV system; when false, they target the nearest/current-room TV.
- `tvLibrarySources` describes approved movie, show, and miscellaneous libraries; `tvProviderSources` describes approved online sources such as Jellyfin and Pluto TV. These entries are server-managed metadata and must not contain credentials.

### Defaults
- Title: `mug`
- Params:
  - `objectKind="mug"`
  - `placement="table"`
  - `material="ceramic"`
  - `fragility="normal"`
  - `condition="intact"`
  - `windowState="closed"`
  - `ownerName=""`
  - `keyId=""`
  - `keyFor=""`
  - `surfaceId=""`
  - `surfaceTitle=""`
  - `repairCost=8`
  - `purchaseCost=14`
  - `replacementHint="A similar everyday replacement would work."`
  - `giftable=true`
  - `description="A small household object."`

### Use
- `use` inspects the object, condition, owner, description, and placement.
- Key objects can describe what they open.
- Window objects report whether they are open or closed; open windows mean outside ambience can carry into the room, while closed windows keep it muffled.
- `secondary use` repairs cracked/broken objects. For windows, `secondary use` toggles open/closed state.

### Validation
- `objectKind`: household item or fixture, including mugs, books, lamps, radios, chairs, couches, beds, tables, counters, shelves, fridges, sinks, stoves, windows, curtains, and rugs.
- `placement`: `floor | table | counter | shelf | wall | ceiling | window | fixture | furniture | appliance | carried`
- `material`: `ceramic | glass | wood | metal | paper | plastic | fabric | plant | mixed`
- `fragility`: `sturdy | normal | fragile | delicate`
- `condition`: `intact | scuffed | cracked | broken | repaired | replacement`
- `windowState`: `closed | open`
- `ownerName`, `keyId`, `keyFor`, `surfaceId`, `surfaceTitle`, `replacementHint`, and `description` are bounded text fields.
- `repairCost` and `purchaseCost` are non-negative integers up to 10000.
- `giftable` accepts boolean/on-off style values.

## `dice`

### Defaults
- Title: `Dice`
- Params:
  - `sides=6`
  - `number=2`
- Global:
  - `useSound=sounds/roll.ogg`
  - `emitSound=none`
  - `useCooldownMs=1000`
  - `emitRange=15`
  - `directional=false`

### Use
- Rolls `number` dice with `sides` sides and reports values + total.

### Validation
- `sides`: integer `1..100`
- `number`: integer `1..100`

## `wheel`

### Defaults
- Title: `wheel`
- Params:
  - `spaces="yes, no"`
- Global:
  - `useSound=sounds/spin.ogg`
  - `emitSound=none`
  - `useCooldownMs=4000`
  - `emitRange=15`
  - `directional=false`

### Use
- Announces spin immediately.
- Result is sent after delay.

### Validation
- `spaces`: comma-delimited values
- At least 1 entry
- Max 100 entries
- Max 80 chars per entry

## `clock`

### Defaults
- Title: `clock`
- Params:
  - `timeZone="America/Detroit"`
  - `use24Hour=false`
  - `topOfHourAnnounce=true`
  - `announceIntervalMinutes=60`
  - `alarmEnabled=false`
  - `alarmTime="12:00 AM"`
- Global:
  - `useSound=none`
  - `emitSound=sounds/clock.ogg`
  - `useCooldownMs=1000`
  - `emitRange=10`
  - `directional=false`

### Use
- Broadcasts a spoken EL640-style time announcement as spatial audio from the clock position.
- Manual `use` announces the current time to the activating user and broadcasts the spatial clock speech sequence.

### Validation
- `timeZone`: one of `CLOCK_TIME_ZONE_OPTIONS` in `server/app/item_catalog.py`
- `use24Hour`: boolean or on/off style input
- `topOfHourAnnounce`: boolean or on/off style input
- `announceIntervalMinutes`: integer from `1` to `60`; `1` announces every minute, `60` announces hourly
- `alarmEnabled`: boolean or on/off style input
- `alarmTime`: `HH:MM` when `use24Hour=true`, otherwise `H:MM AM/PM`
  - Visible only when `alarmEnabled=true` (`visibleWhen: {"alarmEnabled": true}`)

### Audio
- Spoken clock assets live under `client/public/sounds/clock/el640/`.
- The client plays these built-in EL640 clock voice samples by default through the item audio layer, independent of optional browser TTS announcement mode.
- Automatic routine (when enabled) announces on the configured minute interval. Hourly announcements use `hour1.ogg` + time phrase + `hour2.ogg`; more frequent announcements speak the time phrase only.
- Alarm routine (when enabled and time matches) uses `announcement.ogg` + time phrase + `alarm.ogg`.

## `widget`

### Defaults
- Title: `widget`
- Params:
  - `enabled=true`
  - `directional=false`
  - `facing=0`
  - `emitRange=15`
  - `emitVolume=100`
  - `emitSoundSpeed=50`
  - `emitSoundTempo=50`
  - `emitInitialDelay=0`
  - `emitLoopDelay=0`
  - `emitEffect="off"`
  - `emitEffectValue=50`
  - `ambienceScope="tile"`
  - `ambienceName=""`
  - `ambiencePriority=50`
  - `useSound=""`
  - `emitSound=""`
- Global:
  - `useSound=none`
  - `emitSound=none`
  - `useCooldownMs=1000`
  - `emitRange=15`
  - `directional=false`
  - `emitSoundSpeed=50`
  - `emitSoundTempo=50`
  - `emitInitialDelay=0`
  - `emitLoopDelay=0`

### Use
- `use` toggles `enabled` on/off and plays `useSound` when configured.
- Widgets with `emitSound` normally play from their tile. Set
  `ambienceScope="location"` to use the stream as the whole current location's
  ambience bed instead, such as outdoor ambience, mountains, rivers, forests,
  offices, or room tone. A location-scoped ambience widget does not also play as
  a single-tile emitter.

### Validation
- `enabled`: boolean or on/off style input
- `directional`: boolean or on/off style input
- `facing`: number `0..360` with step `1`
- `emitRange`: integer `1..20`
- `emitVolume`: integer `0..100`
- `emitSoundSpeed`: integer `0..100` (`0=0.5x`, `50=1.0x`, `100=2.0x`) for speed/pitch
- `emitSoundTempo`: integer `0..100` (`0=0.5x`, `50=1.0x`, `100=2.0x`) for tempo
- `emitInitialDelay`: number `0..300` with `0.1` step/precision; delay in seconds before emitted audio starts after enable
- `emitLoopDelay`: number `0..300` with `0.1` step/precision; delay in seconds between each emitted loop playback
- `emitEffect`: `reverb | echo | flanger | high_pass | low_pass | off`
- `emitEffectValue`: number `0..100` with `0.1` precision
- `ambienceScope`: `tile | location | off`
- `ambienceName`: bounded text, max `80`
- `ambiencePriority`: integer `0..100`; higher priority wins inside the same location
- `useSound`: empty, filename (assumed under `sounds/`), or full URL
- `emitSound`: empty, filename (assumed under `sounds/`), or full URL
- TappedIn Archive ambience/FX URLs under `https://tappedin.fm/wp-content/uploads/Archive/fx/` are valid full URL values for world-building sounds.

## `billboard`

### Defaults
- Title: `billboard`
- Params:
  - `enabled=true`
  - `billboardMode="interactive"`
  - `itemVisibility="visible"`
  - `headline=""`
  - `body=""`
  - `url=""`
  - `announcementText=""`
  - `voiceName=""`
  - `voiceAssetUrl=""`
  - `bannerText=""`
  - `rotationSeconds=12`
  - `emitRange=12`
- Global:
  - `useSound=none`
  - `emitSound=none`
  - `useCooldownMs=1000`
  - `emitRange=12`
  - `directional=false`

### Use
- `interactive` billboards speak the headline/body, rotating banner lines, announcement text, and URL.
- `display_only` billboards speak the content and report that they are display only.
- `audio_only` billboards prefer the voice announcement text; hidden/audio-only billboards are not rendered or listed as nearby items, but can still provide spoken context.
- Nearby billboard announcements play automatically like public-transit or station announcements. When `voiceAssetUrl` points to a real MP3/OGG file, that voice asset plays spatially from the billboard and keeps updating as the listener walks. Browser speech synthesis is fallback only when no real voice asset is configured or the asset cannot load/decode.

### Validation
- `enabled`: boolean or on/off style input
- `billboardMode`: `interactive | display_only | audio_only`
- `itemVisibility`: `visible | hidden`
- `headline`: max 120 chars
- `body`: max 360 chars
- `url`: empty, absolute public `http/https` URL, or site-relative path
- `announcementText`: max 500 chars
- `voiceName`: max 80 chars
- `voiceAssetUrl`: optional `sounds/` path, site sound path, or public `http/https` MP3/OGG URL, max 2048 chars
- `bannerText`: max 500 chars; separate rotating banner lines with `|`
- `rotationSeconds`: integer `3..300`
- `emitRange`: integer `1..20`

## `piano`

### Defaults
- Title: `piano`
- Params:
  - `instrument="piano"`
  - `voiceMode="poly"`
  - `octave=0`
  - `attack=3`
  - `decay=55`
  - `release=45`
  - `brightness=68`
  - `emitRange=15`
- Global:
  - `useSound=none`
  - `emitSound=none`
  - `useCooldownMs=1000`
  - `emitRange=15`
  - `directional=false`

### Use
- Announces that the user begins playing the piano (client enters piano key mode).
- Piano mode automatically requests MIDI access when the browser allows it, so physical keyboards can play immediately after using the item.
- Piano-style instruments use the real 88-key A0-C8 MIDI range and an acoustic-piano-style hammer/body synth path.
- Piano mode controls include `Z` to start/pause/resume recording (max 30s) and `X` to play saved recording.
- Recordings are stored on the item (server-authoritative), so nearby users hear playback.

### Validation
- `instrument`: `piano | electric_piano | guitar | organ | bass | violin | synth_lead | brass | nintendo | drum_kit`
- `voiceMode`: `poly | mono`
- `octave`: integer `-2..2`
- `attack`: integer `0..100`
- `decay`: integer `0..100`
- `release`: integer `0..100`
- `brightness`: integer `0..100`
- `emitRange`: integer `5..20`
- Instrument changes reset `voiceMode`/`octave`/`attack`/`decay`/`release`/`brightness` to instrument defaults.

## Adding A New Item Type (Plugin Discovery)

Server is the source of truth for item type definitions and metadata. The client consumes server `welcome.uiDefinitions` and only provides UX/runtime behavior.

For a full copy/paste example with plain-English explanation, see `docs/item-type-template.md`.

1. Server item package: add a new folder under `server/app/items/types/<item_type>/` with:
   - `definition.py` (defaults/capabilities/metadata/options)
   - `validator.py` (`validate_update`)
   - `actions.py` (`use_item`)
2. Server plugin: add `server/app/items/types/<item_type>/plugin.py` exporting `ITEM_TYPE_PLUGIN` with:
   - `type`
   - `order`
   - `module`
   The server auto-discovers plugins at boot, so no central registry edit is needed.
3. Server/client protocol/state models are now string-based for item type ids; for generic types no enum/union list updates are required.
5. Client runtime behavior: add `client/src/items/types/<item_type>/behavior.ts` only if custom client runtime is needed (for example piano mode).
6. Tests: add or update server tests under `server/tests/` for use/update validation, unknown-key stripping, and `uiDefinitions` completeness.

### Example Shape

A minimal new item type usually needs:

- Catalog defaults:
  - `default_title`
  - `default_params`
  - `use_sound` / `emit_sound`
  - `use_cooldown_ms`
- Handler behavior:
  - validate params on update
  - build self/others use messages
  - optionally return delayed result text
