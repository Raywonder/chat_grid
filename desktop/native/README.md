# Indiginous Desktop Native

Official accessible wxPython desktop client. The native frame hosts the shared Indiginous web runtime in the installed WebView engine so browser, Windows, macOS, and future platforms keep one world protocol and audio implementation.

- Persistent WebView2 profile retains the blind.software sign-in securely.
- Automatic connect after the retained session is restored.
- Silent bounded reconnect after navigation/network loss; the shared client also reconnects its WebSocket peers.
- Optional per-user Windows startup and minimized startup.
- The full current web/sound asset tree is packaged for macOS fallback and the
  signed PKG. Normal live operation also uses HTTPS caching and quietly
  preloads the published ambience catalog in the background, so missing sounds
  can refill without blocking startup.
- Background update checks use the tCast manifest pattern, require HTTPS and a valid SHA-256, download atomically, install silently after exit, and relaunch only after successful setup.

Build from Windows:

```powershell
.\scripts\build-windows.ps1
```

Artifacts are written to `release/`. Publish the installer first, compute SHA-256, replace the manifest placeholder, and publish the manifest only after its URL, version, filename, and checksum all match.
