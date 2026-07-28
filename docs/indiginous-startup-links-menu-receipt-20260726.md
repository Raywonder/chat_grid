# Indiginous startup links menu receipt — 2026-07-26

The next desktop release must keep the initial Indiginous window focused on the
app name, status, and world surface. Public links are not startup-window
content in the native shells.

Both desktop menu implementations now expose:

- Help > Open Indiginous website — `https://blind.software/indiginous/`
- Help > Open blind.software — `https://blind.software/`

The wxPython and shared native shell source paths were updated, with the links
opened through the system browser only after the user chooses the menu item.

Verification:

- Focused wxPython/native menu tests: 18 passed.
- Python compile checks: passed for both desktop app modules.
- Windows installer rebuild/public publication: pending the next approved
  release build; this change is not claimed as present in an already-published
  installer.
