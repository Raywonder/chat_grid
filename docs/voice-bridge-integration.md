# Voice bridge integration receipt

Updated 2026-07-18 from the Rocco/TeamTalk work.

## Proven upstream voice path

- TeamTalk native bridge runs without Chrome in the middle.
- The ElevenLabs agent WebSocket path is live with `pcm_16000` input and `pcm_48000` output.
- Inbound speech has produced real transcripts, outbound responses have produced real audio, and interrupted playback stops promptly.
- Socket-only reconnect has been observed without leaving TeamTalk.
- The bridge self-test state is recorded in the private OpenClaw state file; the detailed transcript/audio log remains private and is not copied into project documentation.

## Chat Grid wiring

Chat Grid already consumes the compatible pieces through its normal audio architecture:

- microphone/user voice uses the permission-gated WebRTC peer path;
- remote voice is attached to the spatial audio engine and follows the listener position;
- ElevenLabs-generated item, billboard, clock, station, and UI assets use the same spatial/item audio layers;
- interruption, mute, output-device, mono/stereo, and per-peer gain controls remain client-side controls;
- the companion presence is the in-world identity and can send room/direct messages and use world items.

The TeamTalk bridge is not silently treated as a browser WebRTC microphone peer. A future live bridge between those transports must explicitly negotiate a server-side media gateway or an approved in-world audio source. Until that exists, this receipt distinguishes proven TeamTalk voice from proven Grid voice and avoids a false “wired live” claim.

## In-world companion speech

The durable companion now has an additive spatial speech path for its own
generated voice. Appending `{"action":"speak","text":"..."}` to the
companion command stream makes the companion synthesize through the configured
ElevenLabs voice, save the MP3 under `server/runtime/voice/`, and send a
server-validated `agent_voice` packet. Clients fetch the same-origin `/voice/`
asset and play it through the existing spatial sample engine, so distance,
listener position, item-layer mute, and the existing audio cleanup rules apply.

This path is intentionally distinct from WebRTC peer voice and from the
TeamTalk native bridge. It gives the in-world companion a real, spatial,
interruptible voice source without claiming that TeamTalk audio has been
silently converted into a live Grid media gateway.

## Reusable rules

Use the Rocco path as the reference for low-latency speech, interruption, reconnect, quiet/noise gating, speaker identity, and expressive ElevenLabs output. Carry those rules into Grid, VoiceLink, OpenLink, PBX, WhatsApp voice, and future audio surfaces without copying private conversation text or credentials.
