# Indiginous and Jellyfin world media

Indiginous now treats Jellyfin as a server-side media source for in-world TVs
and radios. The player signs in to Indiginous as the person using the world;
the browser never receives the Jellyfin service token.

## Access model

The default deployment uses the non-admin `indiginous-media` Jellyfin account
and applies an Indiginous policy per username. `CHGRID_JELLYFIN_POLICIES` can
grant TV, radio, library, and universal-remote access separately. Unknown
users are denied by default. A later deployment can set
`CHGRID_JELLYFIN_PROVISION_USERS=1` to use background per-user Jellyfin
accounts without changing the world protocol.

The client receives only a capability summary. Playback requests are checked
again by the server and return a server-owned playback route, not a Jellyfin
token. This means a person who can use a radio cannot automatically use a TV,
and a remote can be limited to the media type it controls.

## Realtime TV sequence

An in-world TV can carry a `jellyfinItemId` and optional `jellyfinProgram`
metadata. The response may contain an ordered sequence of:

- `intro`: station ident or opening material from either `Intros` or `intros`;
- `content`: the Jellyfin programme or live channel;
- `break`: material from `Breaks` or `breaks` between programmes;
- `chapters`: chapter titles and offsets for navigation and spoken status.

The browser keeps the TV screen and the normal in-world audio layer together.
When a segment ends, the next segment starts without requiring the user to
leave the room. Live HLS channels continue as live streams; finite programme
segments advance through the sequence.

## Configuration shape

Keep these values in the deployment secret/environment store, never in the
client bundle:

```text
CHGRID_JELLYFIN_URL=https://media.raywonderis.me
CHGRID_JELLYFIN_USER=indiginous-media
CHGRID_JELLYFIN_TOKEN=<server-held token>
CHGRID_JELLYFIN_POLICIES={"alice":{"enabled":true,"canPlayTv":true,"canPlayRadio":true,"libraries":["Indiginous TV","Indiginous Radio"],"universalRemotes":["tv-remote","radio-remote"]}}
```

The live deployment still needs its playback proxy route to exchange the
server-held token with Jellyfin. The world-side permission boundary and
sequence protocol are implemented and tested; deployment of that proxy is a
separate release step.
