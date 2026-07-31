# Indiginious eCrypto menu and pronunciation update

Date: 2026-07-28

## What changed

- Added accepted chat-command aliases `/ecripto`, `/ecr`, and `/ecr*` alongside `/ecrypto`.
- Added eCrypto actions to the keyboard Commands menu: balance, wallet connections,
  help, test funds, wallet connection, and test transfers.
- Menu actions collect needed values through ordinary prompts and submit the
  existing server command path, so users do not need to type slash commands.
- Added speech-friendly pronunciation for eCrypto, eCripto, eCrypto test, TEST-ECR,
  and the supported command spellings while preserving visible/copyable text.
- Added the eCrypto route and aliases to the main help resource.

## Verification

- Client focused tests: 9 passed.
- Client lint: passed.
- Client production build: passed; existing chunk-size warning remains.
- Server eCrypto tests: 7 passed, 110 deselected.
- Python compilation: passed.
- Help JSON validation and `git diff --check`: passed.

This repository already contained unrelated uncommitted widget sound-library and
world work. Those changes were preserved and not reset, cleaned, or folded into
this receipt as a separate feature.
