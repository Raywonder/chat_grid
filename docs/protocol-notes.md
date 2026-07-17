# Protocol Notes

This is a behavior guide for packet semantics beyond raw schemas.

## Direction

- Client packet schema lives in `server/app/models.py` (`ClientPacket`).
- Browser-side validation/parsing lives in `client/src/network/protocol.ts`.
- Keep these synchronized on every protocol change.

## Client -> Server

- `auth_register`: create account with username/password and optional email.
- `auth_login`: authenticate with username/password.
- `auth_resume`: resume prior session via stored session token.
- `auth_logout`: revoke current session and disconnect.
- `welcome_ready`: client confirms it accepted `welcome` preflight and is ready to join active roster.
- `change_location`: move to another server-defined location by id/name. `/go <location>` uses the same server handler. House rooms are regular server-defined locations.
- `admin_roles_list`: request server role list (with user counts + permission sets).
- `admin_role_create`: create role.
- `admin_role_update_permissions`: replace one role permission set.
- `admin_role_delete`: delete role with replacement role reassignment.
- `admin_users_list`: request user list for admin actions (`action`: `set_role | ban | unban | delete_account`).
- `admin_platform_overview`: request platform or owned-content summaries. `scope="platform"` requires server settings permission; `scope="owned_content"` is available to signed-in users and lists only their own items.
- `admin_user_set_role`: set target user role.
- `admin_user_ban` / `admin_user_unban`: disable/enable user account.
- `admin_user_delete`: permanently delete target account.
- `update_position`: client movement intent; server enforces world bounds and movement rate policy.
- `teleport_complete`: client signals teleport landing; server rebroadcasts spatial landing cue.
- `update_nickname`: nickname change request (server enforces uniqueness).
- `chat_message`: player chat.
  - Slash commands include social reactions (`/hug`, `/tap`, `/hi`, `/chat`, `/self`, `/user`, `/highfive`, `/fistbump`, `/cheer`, `/clap`, `/laugh`, `/smile`, `/wink`, `/nod`, `/bow`, `/dance`, `/comfort`, `/pat`, `/poke`, `/boop`, `/salute`, `/thumbsup`, `/heart`, `/sparkle`, `/celebrate`, `/tease`, `/smack`, `/whisper`, `/listen`) and user movement helpers (`/walkto`, `/teleportto`, `/join`).
- `direct_message`: private player chat to a visible peer. The browser queues unsent direct messages across reconnect and re-resolves the target by nickname before retrying.
- `ping`: latency measurement.
- `item_add`, `item_pickup`, `item_drop`, `item_delete`, `item_use`, `item_update`: item actions.
- `item_drop.targetSurfaceId` atomically places a carried surface-safe item on the exact table, shelf, counter, or other open furniture surface selected by the client. The server verifies location, capacity, and item suitability before changing custody.
- `item_transfer_targets`: request transfer target accounts for one item (includes online + offline active users, excluding current owner).
- `item_transfer`: transfer item ownership to another account (`targetUserId` required).
- `item_secondary_use`: trigger type-specific secondary action when implemented.
- `item_piano_note`: realtime piano note on/off for active piano use mode.
- `item_piano_recording`: piano record/playback control (`toggle_record`, `playback`, `stop_playback`).

## Server -> Client

- `auth_required`: authentication challenge after websocket connect.
  - includes `gridName`, `welcomeMessage`, `serverVersion`, and `expectedClientRevision`.
- `auth_result`: auth success/failure and session/account metadata.
- `auth_permissions`: server-pushed live role/permission refresh for current session.
- `admin_roles_list`: role list response payload.
- `admin_users_list`: user list response payload.
- `admin_platform_overview`: platform or owned-content summary payload. Link summaries include author, verification status, owner, item id, location id, and grid coordinates where available.
- `admin_action_result`: structured result for admin actions.
  - admin mutations include `user_delete` for account deletion.
- `welcome`: initial snapshot with users/items plus server UI/world metadata.
  - Server delays roster activation/login broadcast until `welcome_ready` is received.
- `signal`: forwarded WebRTC offer/answer/ICE.
- `update_position`, `location_changed`, `update_nickname`, `user_left`: presence updates.
- `teleport_complete`: peer teleport landing event with spatial coordinates.
- `chat_message`: system and user chat stream.
- `social_action`: structured social/reaction event with action id, actor, optional target, readable message, sound path, and spatial source coordinates.
- `pong`: ping response.
- `nickname_result`: accepted/rejected nickname result.
- `item_upsert`: full item replacement after mutation.
- `item_remove`: item deletion.
- `item_action_result`: action success/failure and user-facing message.
- `item_transfer_targets`: transfer target account list for one item.
- `item_use_sound`: spatial one-shot sound on successful item use (if `useSound` configured).
- `item_game_launch`: game service-link launch from a grid square; clients only auto-open it for players currently on that same square.
- `item_clock_announce`: ordered list of clock speech samples to play sequentially as item-layer spatial audio.
- `item_piano_note`: broadcast piano note on/off with resolved instrument/envelope/spatial params.
- `item_piano_status`: structured piano mode/record/playback state events for client runtime control.

## Item Packet Behavior

- `item_upsert` is full-state replacement for one item, not partial patch.
- `item_upsert.item.display` is server-owned display text for readonly/system properties (for example: `createdBy`, `updatedBy`, `createdAt`, `updatedAt`, `capabilities`, `useSound`, `emitSound`).
- `item_action_result` messages are intended for direct screen-reader/user status feedback.
  - `action` includes: `add`, `pickup`, `drop`, `delete`, `transfer`, `use`, `secondary_use`, `update`
- Successful `item_pickup` and `item_drop` also emit system chat lines to other users in the room.
- Item transfer ownership is account-based; target accounts do not need to be currently connected.
- Piano runtime control no longer depends on parsing `item_action_result.message` text.
- `item_piano_status` carries machine-readable piano events (`use_mode_entered`, record/playback transitions).
- eCrypto bank and wallet actions currently use existing chat and item packets.
  Bank items are stationary, non-carryable service counters seeded across map
  locations; `ecrypto_wallet` items are carryable wallet markers users can keep
  on them while navigating. Logged-in
  users can run `/ecrypto ...` commands for balance, wallet links, test deposits,
  and test transfers; using an `ecrypto_bank` item returns account-specific
  status through `item_action_result`.
- `item_use_sound` contains absolute item world coordinates (`x`, `y`) and sound path.
  - For carried items, source coordinates resolve to the carrier's current position.
- `social_action` contains absolute world coordinates for the reaction sound source. Its sound path is played as a world-layer one-shot.
- `item_clock_announce` contains:
  - `itemId`
  - `sounds`: ordered sample URLs (EL640 phrase parts)
  - absolute source coordinates `x`, `y`
  - generated by server for manual clock `use`, top-of-hour auto announce, and alarm auto announce (when enabled)
  - clients play these built-in clock voice samples by default, independent of optional browser TTS announcement mode
- `teleport_complete` contains absolute player world coordinates (`x`, `y`) at teleport landing.
- Radio metadata (`params.stationName`, `params.nowPlaying`) is server-managed and delivered through normal `item_upsert` updates.
- `item_piano_note` contains:
  - `itemId`, `senderId`, `keyId`, `midi`, `on`
  - resolved `instrument`, `voiceMode`, `octave`, `attack`, `decay`, `release`, `brightness`, `emitRange`
  - absolute source coordinates `x`, `y`

## Welcome Metadata

- `welcome.auth`: authenticated account identity:
  - `authenticated`
  - `userId`
  - `username`
  - `role`
  - `permissions`
  - `policy` (`usernameMinLength`, `usernameMaxLength`, `passwordMinLength`, `passwordMaxLength`)
- `auth_required.authPolicy`: server auth limits advertised before login/register submit.
- `auth_required.gridName` / `auth_required.welcomeMessage`: server-owned pre-login branding values.
- `auth_required.serverVersion`: server diagnostics version text shown in connect/reconnect messaging.
- `auth_required.expectedClientRevision`: authoritative browser asset revision required by this server instance.
- `auth_result.authPolicy`: server auth limits echoed on auth success/failure responses.
- `auth_result.sessionToken` is used by the client to call the instance-scoped HTTP endpoint `GET <base_path>auth/session/set` (`Authorization: Bearer <sessionToken>`, `X-Chgrid-Auth-Client: 1`) so the server can issue an instance-scoped `HttpOnly` session cookie.
- `welcome.worldConfig.gridSize`: server-authoritative grid size used by clients for bounds/drawing.
- `welcome.worldConfig.movementTickMs`: server movement-rate window used for client movement pacing.
- `welcome.worldConfig.movementMaxStepsPerTick`: max allowed grid steps per movement window.
- `welcome.worldConfig.locationId` / `locationName` / `locationDescription`: current location metadata for this session.
- `welcome.worldConfig.locations`: available location list, including the Arcade game area and house interior rooms.
- Location metadata is part of the spatial browsing model: guests and signed-in users can discover public-safe BlindSoftware areas, forum-like squares, billboards, showcases, and software links by moving through the grid and interacting with nearby items.
- `welcome.player`: server-assigned spawn/current self position at connect time.
- `welcome.serverInfo`: server process identity/version metadata:
  - `instanceId`: unique id generated at server startup
  - `releaseVersion`: shared public release version
  - `serverVersion`: server diagnostics version text (`release + server revision`)
  - `expectedClientRevision`: browser asset revision required by this server instance
  - `gridName`: server-owned user-facing grid name
  - `welcomeMessage`: server-owned pre-login welcome string
- `welcome.uiDefinitions`: server-provided item UI definitions:
  - `itemTypeOrder`: add-item menu order
  - `itemTypes[].tooltip`: item-level tooltip/help text
  - `itemTypes[].capabilities`: server-declared actions supported by the type
  - `itemTypes[].editableProperties`: editable property keys by item type
  - `itemTypes[].propertyMetadata`: property-level metadata (`valueType`, optional `label`, optional `range`, optional `tooltip`, optional `maxLength`, optional `options`, optional `visibleWhen`)
  - `itemTypes[].globalProperties`: non-editable global values (`useSound`, `emitSound`, `useCooldownMs`, `emitRange`, `directional`, `emitSoundSpeed`, `emitSoundTempo`, `emitInitialDelay`, `emitLoopDelay`)
  - `commandMetadata.mainModeActions`: server-authored labels/tooltips for server-backed main-mode commands used by the client command palette
  - `itemManagement.actions`: server-authored labels/tooltips and permission-key metadata for item-management actions (`transfer`, `delete`)
  - `adminMenu.actions`: server-authored admin root menu labels/tooltips/ordering for the authenticated user
- Maintainer note: the current server-owned command/menu metadata definitions live in `server/app/ui_metadata.py`.
- Client item UI requires this metadata from the server; there is no fallback item definition map.
- Client property help/type rendering is metadata-driven; it does not infer fallback types/tooltips from hardcoded key heuristics.
- `visibleWhen` supports equality checks and string negation via `!` prefix (example: `{"mediaEffect": "!off"}`).

## Validation Boundaries

- Server is authoritative for all action validation and normalization.
- Server is authoritative for movement acceptance (bounds + rate/delta checks).
- Server persists account state (last nickname + last position) and restores spawn from that state on auth login/resume.
- Server also supports websocket handshake cookie resume:
  - accepts browser sockets only when websocket `Origin` matches `CHGRID_HOST_ORIGIN`
  - websocket and auth helper routes are scoped under the configured `server.base_path`
  - reads the instance-scoped session cookie from the websocket `Cookie` header
  - attempts resume before sending `auth_required`
  - exposes `GET <base_path>auth/session/clear` to expire the `HttpOnly` cookie (`X-Chgrid-Auth-Client: 1` and matching `Origin` required)
- Server applies auth hardening before accepting login/register/resume:
  - login/register PBKDF2 work runs off the event loop in bounded worker concurrency
  - repeated auth failures are rate-limited by IP and IP+identity windows
  - auth failures include small randomized response jitter to reduce high-resolution probing
- Client validates incoming packet shapes and applies runtime behavior.
- Server is authoritative for role/permission checks on every privileged packet.
- `voice.send` permission changes are pushed at runtime via `auth_permissions`.
- Sound/media field normalization uses shared server policy helpers:
  - `none/off` normalize to empty values
  - bare filenames normalize to `sounds/<name>` for sound-reference fields
  - media URL-like fields are trimmed/validated consistently
  - radio stream metadata fetches only follow validated public `http`/`https` URLs and revalidate redirect hops
- Client-side item edit validation is convenience only; server remains source of truth.

## Heartbeat/Stale Recovery

- Client sends automatic heartbeat `ping` packets every 10 seconds while connected.
- Heartbeat pings use negative `clientSentAt` ids and are internal (not user-visible ping status).
- If websocket close is observed unexpectedly, client starts reconnect flow.
- The client reconnects only after sustained heartbeat silence: three missed
  intervals while visible, or nine while the page is backgrounded. A single
  delayed `pong` no longer tears down a healthy world connection.
- `posture_move` carries server-authoritative furniture/floor actions:
  `shift_left`, `shift_right`, `stand`, and `return_to_bed`.
- Reconnect flow waits 5 seconds and retries up to 3 times before stopping.
- After reconnect, if `welcome.serverInfo.instanceId` changed, client announces `Server restarted.`
- Client emits `Connected to server. Version <version>.` on initial `welcome` and
  `Reconnected to server. Version <version>.` after reconnect.
- If `auth_required.expectedClientRevision` or `welcome.serverInfo.expectedClientRevision` differs from the running client revision, client auto-reloads.
- Server-only version changes do not trigger browser reload unless `expectedClientRevision` also changes.
