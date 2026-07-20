# Next Build: Browser Authentication and Audio Device Settings

## Release Goal

Publish the next Endiginous Desktop build through the verified update channel
with browser-based sign-in, secure authentication return to the native client,
and native microphone/output-device settings that control the embedded world.

Deployment remains blocked until the live `blind.software` portal owner and
production SSH/cPanel target are verified. Authentication code and update
manifests must not be deployed to an assumed host.

## Browser Authentication Flow

1. Add **Sign in with browser** to the Endiginous menu and initial signed-out
   experience.
2. Open the system browser at the portal's HTTPS authorization endpoint with a
   generated state value, PKCE challenge, desktop app ID, and registered return
   scheme.
3. Complete the portal's normal login, MFA, account checks, and consent in the
   browser. The portal must offer whichever login methods the user's
   BlindSoftware account has enabled, including Mastodon/fediverse
   authentication when configured. The desktop app never receives the password,
   Mastodon token, OAuth refresh token, or provider callback secret.
4. Return through `chatgrid://auth/callback` with a short-lived authorization
   code and state—not an access token in the URL.
5. Route the callback to the already-running desktop process through local IPC;
   if it is not running, start it and process the callback once.
6. Verify state, exchange the code over HTTPS with PKCE, and create the normal
   Endiginous session.
7. Store only refresh/session material in Windows Credential Manager or macOS
   Keychain. Never store it in `settings.json` or logs.
8. Refresh silently when permitted; otherwise return the user to browser login.
9. Support sign-out, token revocation, account switching, expired callbacks,
   replay rejection, and cancellation.
10. If BlindSoftware local login is not the selected credential method, keep the
    same app flow: the portal resolves the chosen provider to the canonical
    BlindSoftware account, then returns the normal Endiginous authorization code.
    The native client should not special-case Mastodon beyond showing the
    provider label/status returned by the portal.

## Audio Settings UI

Add **Audio Settings…** to the Endiginous/File menu with a standard accessible
dialog containing:

- Output device (speakers/headphones);
- Input device (microphone);
- output volume and mute;
- microphone input level and mute;
- microphone test meter with a text status equivalent;
- output test-sound button;
- refresh-device-list button;
- follow-system-default options for input and output;
- Apply, OK, and Cancel using platform-standard button order.

Controls must have visible text labels, keyboard access, predictable focus,
screen-reader announcements, and no state communicated by a meter or color
alone.

## Native-to-Web Audio Bridge

- The embedded world exposes a versioned `chatGridDesktopAudio` JavaScript API.
- Native code requests device enumeration only after the user grants browser
  microphone permission.
- The web runtime returns opaque device IDs and user-facing labels through the
  bridge.
- Output selection applies `HTMLMediaElement.setSinkId()` to every routed media
  element and to a shared Web Audio output path where supported.
- Input selection restarts only the microphone capture track with an exact
  `deviceId` constraint, then replaces the outgoing WebRTC audio track without
  disconnecting the world session.
- New media elements and reconnects inherit the selected output automatically.
- Device removal falls back to the system default, updates the saved setting,
  and announces the change.
- Unsupported output switching is reported honestly and follows the system
  output rather than showing a nonfunctional selector.

## Native-First Keyboard Input

The native window owns keyboard dispatch before the embedded browser. The File
or Endiginous menu keeps only explicit desktop actions; every other supported key
is offered to the world-input bridge.

### Dispatch order

1. Operating-system reserved and security key combinations remain with the OS.
2. Active native modal dialogs and editable native controls receive their normal
   text-editing/navigation keys.
3. Documented desktop menu accelerators are handled by the native shell.
4. All remaining key-down, key-up, modifier, repeat, and text-input events are
   normalized and forwarded to the embedded world.
5. If the world reports that it did not consume an event, normal native/WebView
   processing may continue where safe.

### Native-only capabilities

- Implement useful world controls that ordinary browser pages cannot reliably
  receive because of browser chrome, focus, or sandbox restrictions.
- Use `EVT_CHAR_HOOK` at the top-level frame so native controls and screen-reader
  hooks do not silently bypass world shortcuts.
- Keep separate physical-key codes and produced text so keyboard layouts,
  dead keys, IME input, and international characters remain correct.
- Forward key-down and key-up consistently to avoid stuck movement/modifier
  states after focus changes.
- Clear held-key state when the window deactivates, minimizes, enters the tray,
  opens a native dialog, or loses the active world.
- Never install a system-wide keyboard hook for ordinary world input.
- Never intercept secure attention sequences, OS accessibility shortcuts, task
  switching, screen-reader commands, or platform-reserved shortcuts.

### Separate native and browser control profiles

Endiginous defines semantic actions once, then supplies distinct bindings for
the native desktop view and browser Web UI. The profiles must not pretend the
two environments reserve the same keys.

- Native desktop may use **Alt+Left** and **Alt+Right** for documented Endiginous
  UI/world navigation because the native shell can consume them before WebView
  browser-history handling.
- The embedded WebView must not navigate backward or forward when those native
  bindings are invoked.
- Browser Web UI uses configurable, conflict-free alternative keys for the same
  semantic actions. It must not override browser history, address-bar, tab,
  refresh, find, developer-tool, or accessibility shortcuts.
- Help, controls, menus, and spoken guidance show the binding for the active
  view—not a mixed list that tells browser users to press native-only keys.
- Persist custom bindings separately as `native` and `web` profiles while
  keeping the underlying action IDs shared.
- When a user moves between browser and native clients, account-synced
  preferences may synchronize action choices and accessibility preferences,
  but platform-reserved key bindings are translated rather than copied blindly.

The first control-map review must inventory all existing web shortcuts before
assigning alternatives. No replacement key is final until collision tests pass
with browser controls, text entry, NVDA, JAWS, VoiceOver, and common keyboard
layouts.

### Menu and discoverability

- File/Endiginous menu commands remain keyboard accessible and list their
  accelerators.
- Add a keyboard-controls/reference action to the Help menu.
- Let users review and change non-reserved world bindings, detect conflicts,
  restore defaults, and choose whether browser-standard shortcuts such as find
  or refresh are reserved by the shell.
- Provide an accessible status message when input mode changes between a native
  dialog, text entry, and world control.

### Bridge contract

- Expose a versioned `chatGridDesktopInput` API beside the audio bridge.
- Send normalized event objects containing event type, physical code, logical
  key, modifiers, repeat state, timestamp, and text when applicable.
- Do not send keystrokes to server logs, analytics, crash reports, or any page
  outside the approved Endiginous origin.
- Disable the bridge on untrusted navigation and restore it only after origin
  and protocol-version validation.
- Keep browser and native control maps synchronized from one versioned control
  definition so behavior does not drift between clients.

## Persistence and Privacy

- Save opaque preferred device IDs in the normal non-secret settings store.
- Do not record microphone labels, audio samples, authorization values, tokens,
  or device IDs in application/server logs.
- Request microphone access only for voice features or an explicit microphone
  test.
- Show and persist separate microphone mute and output mute states.

## Server and Portal Work

- Register the desktop app and exact `chatgrid://auth/callback` return URI.
- Add authorization-code issuance with PKCE, short expiry, single consumption,
  state verification, and destination/client binding.
- Add code exchange, refresh, revocation, and account-session endpoints.
- Add provider discovery to the authorization endpoint so web/native clients
  can use the login methods configured on the BlindSoftware account, including
  Mastodon/fediverse OAuth when enabled.
- Resolve every external provider login to a verified canonical BlindSoftware
  account before issuing an Endiginous code. Do not let a Mastodon handle or
  domain become the Endiginous account identity by itself.
- Keep provider tokens and refresh credentials in the portal credential store
  only. Do not send them to the Endiginous world server, desktop client,
  installer logs, crash logs, or update manifests.
- Expose account notification preferences to the Endiginous session so clients
  can manage shared in-grid/ntfy settings from the signed-in account.
- Generate browser-to-app return pages with a manual **Return to Endiginous**
  link when automatic protocol opening is blocked.
- Publish signed/checksummed Windows and macOS update metadata only after both
  artifacts pass launch, authentication, audio, reconnect, and rollback tests.
- Place artifacts behind the authenticated private-download system while
  preserving updater access through short-lived authorized download URLs.

## Acceptance Tests

- Browser sign-in returns to the existing client process without opening a
  duplicate world window.
- Passwords and reusable tokens never appear in callback URLs or logs.
- Invalid state, reused codes, wrong client IDs, expired codes, and wrong PKCE
  verifiers fail safely.
- Local BlindSoftware login, Mastodon/fediverse login, and a user whose local
  login is disabled but Mastodon login is enabled all complete through the same
  native callback and session creation path.
- Provider revocation, provider mismatch, and an unlinked Mastodon account fail
  accessibly without leaking provider tokens or raw callback values.
- Silent refresh survives an ordinary connection drop and application restart.
- Account-backed ntfy preferences load after sign-in, save from App settings,
  survive client restart, and fall back to in-grid notifications if ntfy is
  disabled or unavailable.
- Output test audio plays through the selected device.
- Existing and newly-created world sounds follow the selected output.
- Microphone test and WebRTC voice use the selected input.
- Changing microphones replaces the outgoing track without leaving the world.
- Removing a selected device falls back cleanly and accessibly.
- Windows/NVDA and macOS/VoiceOver keyboard flows pass.
- World controls receive native key-down/key-up events, including approved keys
  unavailable to an ordinary browser page, while menu, text-entry, OS, and
  screen-reader shortcuts retain correct behavior.
- Alt+Left and Alt+Right perform their documented Endiginous actions in the
  native client without triggering WebView history. Browser Web UI exposes and
  documents tested alternative bindings for those same actions.
- Native and web help surfaces announce only their active control profile and
  remain behaviorally consistent through shared semantic action IDs.
- Losing focus or hiding in the tray clears held keys and never leaves movement
  or modifiers stuck.
- The old build remains available for immediate rollback until update adoption
  and authentication health are verified.
