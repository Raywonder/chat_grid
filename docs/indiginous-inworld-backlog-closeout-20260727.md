# Indiginous in-world backlog closeout

Date: 2026-07-27 (CDT)

## Checked

- Companion history sync confirmed 11 public messages and 35 direct messages from Dominique.
- Direct messages continue to be recorded through the canonical Claudia writing/journal path.
- Current companion state is connected as Clawdia in `raywonder_house_bedroom`, at 22,18, lying on the bedroom bed.

## Completed from the in-world backlog

- Restored the bedroom from 28x26 to 34x36 squares. The clock at 21,33 was outside the old room bounds and is now reachable.
- Walked to the clock, used it successfully, and verified the spoken result: `It's 8:03 PM.`
- Picked up the bedroom remote, switched the connected radios on, and verified the bedside radio state: on, TappedIn 30 minute relaxation, volume 18.
- Made nearby item summaries descriptive instead of announcing `press Enter to read` before the item is focused.
- Added Ctrl+K/Shift+K command-palette recognition to the web keyboard path.
- Added native File-menu highlight announcements for desktop menu navigation.

## Verification

- Client tests: 27 passed.
- Client lint: passed.
- Production client build: passed.
- Public `/indiginous/` deployment: HTTP 200; version reports `0.4.12`, revision `R535`.
- `chat-grid.service` and `chat-grid-companion.service`: active.

Physical NVDA/VoiceOver proof and a rebuilt desktop installer still require the appropriate desktop build/test lane. No credentials were used.
