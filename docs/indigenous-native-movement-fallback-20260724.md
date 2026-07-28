# Indiginous native movement fallback — 2026-07-24

## Finding

The web client movement repair was present in source and production, but the
installed native shell had a separate Windows input failure path. When
`RegisterHotKey` could not claim an arrow key, the shell logged the failure and
left no usable fallback. This produced the observed state where Tab could
announce held items but arrow movement did nothing.

## Change

The native wxPython shell now installs its existing foreground-only
`WindowsWorldKeyHook` when Windows global arrow registration fails. The hook
only captures arrows while the Indiginous process is foreground, forwards the
same `chatGridNativeKey` path as the normal native bridge, and is closed again
when world hotkeys are deactivated.

## Verification

- Native source syntax check passed with `py_compile`.
- Native keyboard/accessibility source tests passed: 6 tests.
- Web client tests passed: 26 tests.
- Web client lint passed.
- Web client production build passed.
- Live companion was ready and connected in `raywonder_house_living_room`.
- Windows VM access passed (SSH/RDP/build share available).

## Still required before calling the installed app fixed

- Rebuild the native Windows installer from this source on `OPENCLAW-WIN11`.
- Install it in the VM and verify authenticated arrow movement with the real
  WebView/NVDA path.
- Build/verify the matching macOS package on the Mac mini if the native source
  is shipped there.
- Publish only after artifact preflight, install proof, checksums, and public
  download checks pass.

