# Runtime Flow

## Connect Flow

1. User clicks connect.
2. Client validates auth form and sets up local media.
3. Client connects signaling websocket from the configured app origin.
4. Server accepts the socket only on the configured instance websocket path and when the browser `Origin` matches `CHGRID_HOST_ORIGIN`, then attempts cookie-based session resume from the instance-scoped websocket handshake cookie.
5. If resume does not authenticate, server sends `auth_required`.
   - includes `gridName` and `welcomeMessage` for pre-login branding.
   - includes `serverVersion` and `expectedClientRevision` for stale-client detection before login.
   - includes `authPolicy` limits for username/password.
6. Client sends `auth_login` or `auth_register` (or explicit `auth_resume` if provided by caller).
   Future portal-backed clients should treat this as the local/direct fallback:
   the preferred browser/native flow asks the BlindSoftware portal for an
   account-auth route, lets the user use any login method enabled on that
   account such as local login or Mastodon/fediverse authentication, and returns
   a short-lived Endiginous authorization code or handoff for the canonical
   account.
7. Server sends `auth_result`.
   - includes role + permissions for authenticated session.
   - includes canonical account claims; external-provider secrets such as
     Mastodon access/refresh tokens must never be included.
8. Client persists authenticated session into instance-scoped server-managed `HttpOnly` cookie helpers under the active app base path via `GET <base_path>auth/session/set` (`Authorization: Bearer <sessionToken>`, `X-Chgrid-Auth-Client: 1`), and clears it via `GET <base_path>auth/session/clear` on logout/session errors.
   - the optional PHP media proxy validates that same cookie through `GET <base_path>auth/session/check` before relaying media
9. Server sends `welcome` with users/items snapshot.
10. Client:
   - applies `welcome.worldConfig.gridSize` for authoritative grid bounds/rendering
   - applies `welcome.worldConfig.movementTickMs` as movement pacing guidance
   - applies `welcome.worldConfig.movementMaxStepsPerTick` for movement-rate parity
  - receives current location metadata and the server-defined location list
  - starts the current location's procedural ambience when the world audio layer is enabled
   - uses `welcome.player` as authoritative starting position (restored from server-side account state when available)
   - records `welcome.serverInfo` (`instanceId`, `releaseVersion`, `serverVersion`, `expectedClientRevision`, `gridName`, `welcomeMessage`) for restart detection and client branding
   - if `welcome.serverInfo.expectedClientRevision` differs from the running client revision, auto-reloads the page
   - applies `welcome.uiDefinitions` for item menus/properties/options, server-backed command metadata, item-management metadata, and admin menu labels/order
   - sends initial `update_position` echo from server-assigned starting tile
   - sends initial `update_nickname`
   - creates peer runtimes for known users
   - syncs item runtimes (`radio`, `emit`)
   - applies audio layer state
   - starts signaling heartbeat monitor
   - starts game loop

## Main Loop

Each frame:

- Handle local movement input.
- Send movement intents; server remains authoritative on accepted movement updates.
- Open shared game launches only when the server launch packet matches the player's current grid square.
- Keep the current location ambience in sync with the world audio layer and active location.
- Update spatial voice audio.
- Update spatial radio audio.
- Update spatial item emit audio.
- Draw canvas scene.

## Message Handling

Core incoming message effects:

- `signal`: WebRTC negotiation and ICE exchange.
- `auth_required`: prompt client to authenticate before gameplay messages.
- `auth_result`: auth success/failure with optional session token + account metadata + `authPolicy`.
- `auth_permissions`: live permission refresh (role + permission set) after role/permission admin changes.
- `admin_roles_list`: role metadata + user counts + permission keys for role management UI.
- `admin_users_list`: user metadata list for role/ban admin flows.
- `admin_action_result`: success/error for role/user admin mutations.
- `update_position`: update peer position; may play movement/teleport world sound.
- Guarded house entry validates immutable signed-in identity plus the configured keypad policy on the server. Blank Enter and a copied display name never bypass that policy. Occupants and owner notification routes are alerted; verified residents enter immediately and verified guests enter after ten seconds.
- A server background loop occasionally drifts one eligible teleport pad by one safe, unblocked cardinal square and broadcasts the authoritative item position.
- `location_changed`: reset local room state for the new location, switch the local ambience bed, or add a peer arrival.
  House interiors and their rooms use the same server-owned location flow as city, town, arcade, and offices.
- `teleport_complete`: play peer teleport landing sound at final tile.
- `update_nickname`: update peer display name.
- `chat_message`: append/readable status; optional system sound class.
- Outbound room chat and direct messages use a bounded browser outbox. If the websocket is closed during a send, the message is kept in local storage and retried after the next `welcome`. Direct messages keep the intended target name so reconnect can resolve the target's current peer id when that user is visible again.
- `social_action`: append/readable structured reaction text and play the configured spatial reaction sound.
- `item_upsert`: replace item snapshot and resync item runtimes.
- `item_remove`: remove item and cleanup runtimes.
- `item_action_result`: success/error status for actions.
- `item_use_sound`: play one-shot spatial sample (world layer gated).
- `item_piano_note`: start/stop synthesized piano notes from remote users (item layer gated).
- `item_piano_status`: structured piano mode/record/playback transitions (client runtime state).
- `pong`:
  - positive `clientSentAt`: user ping response (`P` command)
  - negative `clientSentAt`: internal heartbeat response

## Stale Connection Recovery

- If websocket closes unexpectedly, client starts reconnect flow immediately.
- While running, client also sends heartbeat `ping` every 10 seconds (fallback for silent half-open cases).
- If one heartbeat `pong` is missed (10-second interval), client starts reconnect flow.
- Reconnect flow waits 5 seconds and retries up to 3 times.
- If reconnect lands on a different `welcome.serverInfo.instanceId`, client announces server restart.
- Connect/reconnect status message is emitted from `welcome` and includes server version.
- On a valid `welcome`, the client sends `welcome_ready` before doing heavier app-level world/audio setup so the server can activate the authenticated session immediately.
- Server-only deploys no longer force browser reloads unless `expectedClientRevision` changes.
- Pending room/direct chat messages are flushed after the new `welcome` snapshot arrives. Messages whose direct-message target is not visible remain queued instead of being discarded.
- A reconnect `welcome` clears stale WebRTC peer connections, local radio stream runtimes, item emit runtimes, and media retry cooldowns before rebuilding from the fresh world snapshot. After microphone/audio setup returns, nearby stream subscriptions are forced again so shared radios/items do not stay half-recovered. Forced media syncs also nudge existing paused/errored shared radio and item-loop elements back into playback instead of leaving them in an old retry state.

## Authorization Runtime

- Server enforces item/chat/nickname/voice/admin permissions for each packet.
- Role and permission changes apply live to connected users without reconnect.
- `voice.send` revocation is pushed immediately via `auth_permissions`; client mutes outbound voice track.

## Disconnect/Cleanup

On disconnect:

- Close signaling.
- Stop heartbeat monitor.
- Stop local media tracks.
- Cleanup peers and all audio runtimes.
- Drop any carried items on the user's last tile without changing shared item power state. Active radios and TV objects remain on unless a user explicitly switches them off.
- Reset UI/mode state and lists.

## Runtime Components

- `PeerManager`: peer connection lifecycle and remote track attach.
- `RadioStationRuntime`: shared stream sources + per-item output/effects/spatialization.
- `ItemEmitRuntime`: per-item looping emit source + spatialization.
- `AudioEngine`: shared audio context, samples, effects, voice graph.
## Client update freshness

The browser client loads `/version.js` as the shared release metadata source and also polls it while the page is open. The poll uses timestamped `no-store` requests so Chrome does not keep an old entrypoint after rapid deploys. The watcher checks both the live `CHGRID_CLIENT_REVISION` and the live HTML module asset URL; this catches stale tabs where an old hashed bundle sees a fresh `version.js` value and would otherwise think it is current. When either value differs from the running client, the client announces the update, reloads through a cache-busted URL, and the refreshed page automatically starts the normal connect flow.
