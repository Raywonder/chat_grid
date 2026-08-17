# Agent Connection and Release Contract

This is the canonical safety contract for Claude Code, Codex, OpenClaw workers,
Windows/WSL agents, Mac agents, and any other approved worker touching this
workspace or one of its products.

## The hard rule

An agent must not change, build, publish, deploy, or replace an artifact until
it has confirmed that it is working from the current approved source snapshot.
If the snapshot changes while the agent is working, the agent must stop,
re-read the current rules and receipts, and reacquire ownership. It must never
silently continue from an old checkout, copied folder, stale VM, cached build,
or yesterday's artifact.

## Required connection sequence

Before connecting to a project or resuming work, every agent must:

1. Read the applicable root and project `AGENTS.md`, this contract, the latest
   relevant memory/receipt, and any active handoff.
2. Confirm the exact host, account, node, repository, branch, working tree, and
   target surface.
3. Check whether another agent already owns the task. One repository has one
   active editing owner unless the task lead explicitly divides the work.
4. Run `scripts/agent_sync_guard.py connect --repo PATH --agent NAME` and keep
   the resulting claim for the duration of the work.
5. Re-run the guard before a build, release, deployment, or handoff.

If any check is unavailable, contradictory, or stale, the correct action is
**stop and report the blocker**, not guess.

## Ownership and stale-state rules

- The active claim records the source commit and working-tree fingerprint.
- Another worker must not edit the same repository while a claim is active.
- A host-local claim whose recorded owner PID no longer exists may be taken
  over by a new worker after inspecting the current source and working-tree
  fingerprint. Claims from a live process or another host remain protected
  until they expire or the owner explicitly releases them.
- A changed commit, changed tracked files, changed release metadata, or changed
  relevant source tree invalidates the claim. The worker must stop and reacquire.
- A worker may inspect another worker's files, but must not overwrite, reset,
  clean, stash, switch branches, or publish over them to make its own work fit.
- Recovery points are required before risky edits. Keep them; do not delete a
  previous agent's recovery point merely to tidy the directory.
- A development build is not a release. Never promote a staged or cached
  artifact unless its source fingerprint, version, revision, target platform,
  and checksum match the current release receipt.

## Product and platform separation

These defaults apply to every app unless Dominique explicitly changes them:

- Desktop and mobile builds are separate products/surfaces even when they share
  a numeric build number.
- Desktop features must be verified in the desktop source and desktop artifact;
  mobile features must be verified in the mobile source and mobile artifact.
- For VoiceLink, Windows and macOS desktop builds come only from the VoiceLink
  websites. The iOS build comes only through the App Store/TestFlight. Never
  install or distribute the iOS build on macOS.
- Do not infer feature parity from matching version/build numbers.
- For Indiginous, preserve the existing Windows installer filename exactly:
  `Indiginous_Setup.exe`. Do not rename it to match a release number or a
  temporary product spelling.
- Product names and URL paths are separate contracts. Preserve tokenized URL
  rules and existing compatibility paths unless a coordinated migration has
  been approved and verified.

## Release gate

Only the task/project lead may publish or replace a user-facing artifact, and
only after the receipt contains:

- the exact source commit/tree fingerprint and agent/node;
- the version and platform-specific revision;
- focused tests plus the relevant complete test/build gate;
- artifact path, stable filename, size, and SHA-256;
- the actual upload/deploy result;
- user-facing verification from the correct platform and URL/store surface;
- explicit remaining limitations.

If the source is dirty, the receipt must identify the exact intentional dirty
changes and the claim must still match. If a release check fails, do not work
around it by publishing an older artifact.

## Handoff and recovery

Every worker leaving work unfinished must leave a concise handoff with what was
verified, what changed, what remains, the active claim/repository, and the next
safe command. Aborted, timed-out, disconnected, or stale runs are retry
conditions from the last verified checkpoint—not permission to start over from
an unknown copy.

This contract is deliberately boring at the boundary. Boring boundaries keep
the useful, creative work from being replaced by another mystery release.
