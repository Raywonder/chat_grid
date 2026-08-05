# Indiginous housekeeper local-NPC autonomy

Implemented a server-authoritative autonomy layer for `house_keeper` items.

## What is now supported

- quiet private-room NPC cycles alongside the existing repair loop;
- deterministic room movement when no model is enabled;
- movement through a nearby open door or portal to another private interior;
- bounded awareness of nearby signed-in people, other keepers, and nearby items;
- safe in-world speech and task-board ideas;
- optional localhost-only Ollama-compatible JSON decisions;
- reviewed web-discovery intake through `CHGRID_HOUSE_KEEPER_DISCOVERIES_FILE`;
- model timeouts, malformed JSON, non-loopback URLs, and unknown actions all fall
  back to a harmless inspection/keep-watch result.

The model can choose only `wait`, `move`, `inspect`, `say`, or `task`. It cannot
run shell commands, follow arbitrary URLs, send outside messages, touch accounts,
or claim to repair physical devices. Web-capable agents can research ideas
outside the world and place short reviewed suggestions in the local JSON handoff;
the world server only imports the text into the keeper's bounded task board.

## Verification

- Focused housekeeper/server tests: **45 passed**.
- Full server suite: **273 passed, 2 existing unrelated failures**.
  The remaining failures are an existing `journalFolder` UI metadata mismatch and
  an existing guarded-house denial expectation in the dirty shared tree.
- Python bytecode compilation passed for the changed server modules.
- Ruff could not start in this environment because the installed executable is
  not runnable (`Permission denied`); no lint result is claimed.

## Runtime configuration

Keeper fields are opt-in/configurable through the item properties:

- `autonomyEnabled` defaults on for private-house keepers;
- `localModelEnabled` defaults off;
- `localModelUrl` defaults to `http://127.0.0.1:11434/api/chat` and is enforced
  as loopback-only;
- `localModelName` defaults to `llama3.2:3b`;
- `webDiscoveryEnabled` defaults off;
- `taskBoard` is capped at 12 short ideas.

The live production service was not replaced in this receipt because the shared
repository remains broadly dirty and the complete suite still contains the two
pre-existing failures above. The safe next release step is to resolve or accept
those baseline failures, run the server release gate, then restart the server
and verify a keeper cycle from the authenticated user path.
