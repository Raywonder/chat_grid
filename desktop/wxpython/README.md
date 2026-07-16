# Chat Grid Windows Native

Official accessible wxPython Windows client. The native frame hosts the shared Chat Grid web runtime in the installed Edge WebView2 engine so browser, Windows, and future platforms keep one world protocol and audio implementation.

- Persistent WebView2 profile retains the blind.software sign-in securely.
- Automatic connect after the retained session is restored.
- A conventional native File menu reachable with Alt+F, including reconnect,
  frozen-world recovery, world focus, settings, tray minimize, and exit.
- Software-rendered WebView2 by default to avoid GPU-driver lockups on older
  Windows systems; a stalled renderer can be replaced without restarting Windows.
- Silent bounded reconnect after navigation/network loss; the shared client also reconnects its WebSocket peers.
- Optional per-user Windows startup and minimized startup.
- The full current web/sound asset tree is packaged from `../windows/web` for fallback. Normal live operation uses WebView2 HTTP caching, which downloads only resources the current world requests.
- Background update checks use the tCast manifest pattern, require HTTPS and a valid SHA-256, download atomically, install silently after exit, and relaunch only after successful setup.

Build from Windows:

```powershell
.\scripts\build-windows.ps1
```

Artifacts are written to `release/`. Publish the installer first, compute SHA-256, replace the manifest placeholder, and publish the manifest only after its URL, version, filename, and checksum all match.
