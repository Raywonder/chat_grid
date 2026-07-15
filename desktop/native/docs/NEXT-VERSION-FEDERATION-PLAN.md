# Chat Grid Next-Version Federation Plan

## Goal

Let a user sign in once through the official portal and enter Chat Grid without
knowing which domain currently hosts the selected world. A client may begin at
`blind.software` and be quietly handed to any approved, healthy Chat Grid
instance, provided that instance is federated, current, and has the assets
required by the destination world.

An instance may be another hosted account and domain on the same physical
server, another isolated backend on that host, a separate physical machine, a
virtual machine, a VPS, a container, or another supported internal backend.
Federation is based on registered instance identity and capabilities—not on a
specific domain name or hosting topology.

This is a plan for the next release. It must not alter the stable 0.2.1 client
until the protocol, security model, rollback path, and compatibility tests are
complete.

## User Experience

1. The user opens the web or native client and chooses **Connect**.
2. The client opens the central portal login when no valid session exists.
3. The portal resolves the account, requested world, permissions, and best
   available federated server.
4. The portal returns a short-lived, single-use handoff—not a password or
   reusable portal session.
5. The client connects directly to the selected server and loads that server's
   verified world assets.
6. If that host becomes unavailable, the client requests another route and
   reconnects quietly when a compatible replica is available.
7. Domain names, ports, server credentials, and federation details stay out of
   normal end-user configuration.
8. Moving to a world hosted by another instance feels like moving through an
   ordinary internal doorway; routing and session transfer happen behind the
   scenes.

## Architecture

### Portal and identity authority

- Maintain one canonical account identifier per person.
- Keep passwords, MFA, recovery, subscription status, bans, and account
  ownership authoritative at the portal.
- Give each hosted server its own revocable machine identity and signing keys.
- Synchronize only the account claims a server needs: canonical user ID,
  display identity, roles/entitlements, moderation state, and claim version.
- Never replicate password hashes, recovery secrets, portal cookies, or MFA
  seeds to world servers.

### Federation registry

The portal keeps an allowlisted registry containing:

- stable server ID and approved domains;
- public HTTPS and secure WebSocket endpoints;
- server signing-key fingerprint and rotation metadata;
- protocol/client compatibility range;
- available world IDs and asset-manifest hashes;
- capacity, region, health, maintenance, and drain state;
- last successful synchronization and replication status.

Only registered servers with valid TLS, current health, matching protocol
versions, and synchronized assets may receive users.

Multiple registered instances may share one physical host and IP when each has
a distinct instance ID, domain or routed path, storage boundary, process/runtime
boundary, health record, and revocable machine credential. Conversely, one
logical world may have compatible replicas across unrelated hosts.

### Doorway and destination routing

- Give every cross-world doorway a stable destination world ID rather than a
  hard-coded domain, IP address, or port.
- Let the portal/federation directory resolve that world ID to the best eligible
  instance at the moment the doorway is used.
- Treat a same-process room move, another hosted account on the same machine,
  and a move to a remote VM/VPS as the same client-level transition.
- Preserve portable identity, inventory, permissions, and return-location data
  in the handoff contract; keep destination-specific live state authoritative
  on the destination instance.
- Prefetch the destination's minimal manifest and connection metadata when a
  user approaches or selects a doorway, without exposing infrastructure details.
- If no eligible destination is available, keep the user safely in the current
  world and announce that the doorway is temporarily unavailable.

### Quiet handoff protocol

1. Client requests a route using the portal-authenticated browser session or a
   registered `chatgrid://connect` link.
2. Portal selects a compatible server from the federation registry.
3. Portal creates a signed, audience-bound, single-use handoff grant with:
   canonical user ID, destination server ID, world ID, permissions, issue and
   expiry times, nonce, account-claim version, and protocol version.
4. The destination exchanges the grant through a server-to-server back channel
   or validates it against the portal's published signing key.
5. The destination consumes the nonce atomically, creates a local session, and
   returns a new destination-scoped session credential.
6. The client discards the handoff grant and connects to the destination's
   advertised secure WebSocket endpoint.

Handoff grants must expire quickly, be single use, be bound to one destination,
and never appear in application logs, analytics URLs, referrers, or crash
reports.

### World and asset synchronization

- Give every world an immutable content revision and signed asset manifest.
- Replicate required assets before advertising a world as routable.
- Verify size and SHA-256 for every replicated asset.
- Keep versioned assets immutable so connected clients are not broken by a
  partial deployment.
- Mark a server ineligible when its world revision, manifest, or protocol range
  does not match.
- Download assets on demand with bounded concurrency and local caching; do not
  download unrelated worlds.
- Allow an origin fallback only for explicitly public, integrity-checked assets.

### Cross-server state

- Keep authoritative world simulation on the server currently hosting the
  user's session.
- Define ownership for persistent inventory, profile, entitlements, contacts,
  moderation, and world state before implementing synchronization.
- Use versioned events with idempotency keys for replicated state.
- Resolve conflicts deterministically and retain an audit trail.
- Do not attempt silent multi-master replication of security-sensitive account
  state.

### Health routing and reconnection

- Use active health checks plus capacity and synchronization readiness.
- Apply circuit breakers so clients are not repeatedly routed to a failing host.
- During failure, request a fresh portal route instead of reusing an expired
  handoff.
- Resume only portable state; never pretend volatile world state survived when
  it did not.
- Explain prolonged outages accessibly while keeping ordinary short reconnects
  quiet.

## Security and Governance Gates

- Complete a federation threat model before production implementation.
- Back up portal/auth databases before schema changes.
- Confirm production targets twice before modifying portal authentication or
  account synchronization.
- Use mutually authenticated server-to-server traffic or independently signed
  requests with replay protection.
- Support key rotation, immediate server revocation, nonce replay detection,
  rate limiting, and security audit logs.
- Keep secrets in the approved credential store and out of repositories,
  installers, manifests, URLs, and client logs.
- Treat a compromised hosted server as unable to mint portal identities or
  grants for any other server.

## Delivery Phases

### Phase 1: Protocol and threat model

- Define canonical IDs, discovery documents, signed claims, handoff messages,
  compatibility negotiation, error codes, and revocation behavior.
- Produce sequence diagrams and abuse-case tests.

### Phase 2: Multi-topology development federation

- Federate non-production instances representing two domains/accounts on one
  physical host and at least one instance on a separate VM, VPS, or machine.
- Prove health selection, single-use handoff, account mapping, asset readiness,
  doorway traversal, reconnect, revocation, and rollback without production
  accounts.

### Phase 3: Portal and server implementation

- Add registry, machine enrollment, health ingestion, route selection, grant
  issuance, account-claim synchronization, and administrative audit views.
- Add server grant consumption, nonce storage, destination sessions, world
  advertisements, and signed asset manifests.

### Phase 4: Client implementation

- Replace the fixed server assumption with portal discovery and route refresh.
- Preserve browser-based authentication and registered `chatgrid://` launch.
- Add silent compatible failover, accessible outage status, and advanced
  diagnostics that never expose grants or credentials.

### Phase 5: Staged production rollout

- Start with internal accounts and one replicated test world.
- Exercise server drain, host loss, stale assets, clock skew, expired grants,
  revoked servers, and version mismatch.
- Expand gradually with metrics and an immediate switch back to single-server
  routing.

## Acceptance Criteria

- A signed-in user can enter a world hosted by any approved compatible instance
  without entering server addresses or signing in again.
- The same doorway flow works for another instance on the current physical host,
  a separate hosted account/domain, and an instance on another VM/VPS/machine.
- Passwords and reusable portal sessions never reach hosted world servers.
- Replaying or redirecting a handoff grant fails.
- An unhealthy, revoked, incompatible, or asset-incomplete server receives no
  new sessions.
- A healthy compatible replica can receive a fresh routed reconnection.
- Windows, macOS, and browser clients follow the same discovery contract.
- Keyboard and screen-reader users receive equivalent login, routing, outage,
  and recovery information.
- Federation can be disabled at the portal to restore stable single-server
  operation without releasing a new client.

## Explicit Non-Goals for the First Federation Release

- No password database replication between hosted servers.
- No arbitrary user-entered server URLs in the standard UI.
- No automatic trust of a domain merely because it runs Chat Grid software.
- No transparent migration of volatile live-world state unless that state has a
  separately designed, tested replication contract.
- No production rollout before the multi-topology development federation passes
  replay, revocation, failure, accessibility, and rollback tests.
