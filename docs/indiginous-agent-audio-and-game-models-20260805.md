# Indiginous agent audio and game-model setup

The live world keeps peer microphone audio on WebRTC. Agent recordings can be
processed offline or in a worker with `server/tools/indiginous_audio_isolate.py`:

```sh
cd server
python3 tools/indiginous_audio_isolate.py recording.wav runtime/stems --backend auto
```

`auto` prefers a local Moises-compatible wrapper and falls back to Demucs. The
Moises adapter is intentionally a command contract because there is no Moises
CLI installed on this host. A wrapper must accept `{input}`, `{output_dir}`,
`{voice_output}`, and `{world_output}` and write both WAV files. Demucs uses
`--two-stems=vocals`, producing a voice stem and a `no_vocals` world-sound
stem. This is suitable for agent hearing/transcription jobs; it is not a
claim of zero-latency WebRTC speaker diarization.

The local Ollama game companion is exposed through
`server/app/game_agent_service.py` and the JSONL-friendly helper:

```sh
python3 server/tools/indiginous_game_agent.py game-context.json
```

The default model is `qwen3:8b`, with `qwen3:4b` as fallback. The model emits
bounded intent (`observe`, `move`, `speak`, `interact`, `use_item`,
`open_game`, or `wait`); the world/companion must still validate and execute
those intents. It cannot run shell commands, invent credentials, or directly
perform irreversible actions.

The service follows `CHGRID_OLLAMA_URL` when set, otherwise the host's
`OLLAMA_HOST` (with `/api/chat` appended), then `127.0.0.1:11434`.

Install registration is host-aware. `deploy/scripts/install_server.sh` writes
`CHGRID_SHARED_TOOL_ROOT` into each server's `.env`; a second Indiginous server
on the same box resolves the existing shared Demucs executable or Moises-style
wrapper instead of making a private copy. Ollama is always treated as one host
service. Run `deploy/scripts/install_agent_tools.sh` directly when the host
administrator wants to install Demucs once with `CHGRID_INSTALL_DEMUCS=1`.

On 2026-08-05 the host has Ollama 0.32.5 and `qwen3:8b`/`qwen3:4b` already
available. Demucs and a Moises CLI are not installed here, so the source and
shared-host registration are complete but actual voice/world separation still
needs one approved backend installation.
