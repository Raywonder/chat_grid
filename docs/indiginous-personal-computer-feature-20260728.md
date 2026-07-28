# Indiginous personal-computer world objects — 2026-07-28

Implemented and committed in `175459942b6c8cdcd7e17eb4b9d10c11ed2cac3a`.

Personal computers are now available as persistent `house_object` items. Each
computer keeps its own platform, operating system, power state, and optional
profile in world item state. The server validates realistic indoor placement
on a desk, table, counter, or workstation furniture. Using a computer reports
its individual configuration; the secondary action wakes it or puts it to
sleep without changing global application settings.

Verification:

- Focused server tests: 27 passed.
- Client item narration test: 5 passed.
- Client ESLint: passed.
- Client production build: passed.
- `git diff --check`: passed for the logical change; existing staged legacy
  packaging files reported pre-existing trailing-whitespace warnings.
- World companion: connected and ready in `offices` at the time of handoff.
- Full server-suite invocation reached the existing server-message tests but
  did not emit a final pytest summary in the available run; it is not claimed
  as a complete pass.

No production publish or installer replacement was performed.
