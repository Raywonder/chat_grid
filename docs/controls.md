# Controls Reference

This document is the authoritative keymap for the client.

## Normal Mode

When you join the grid, the page also shows a compact dashboard with your current coordinates, connected user count, item count, and anything sharing your current square.

### Movement
- `Arrow Keys`: Move. The status reader narrates movement in an interactive-fiction style, such as the direction walked, current room/location, coordinates, surface, nearby people, and items on the square.
- `G`, `Ctrl+G`, or `Shift+G`: Open the location list; use arrows or first letters, then `Enter` to travel
- `Shift+K`, `Applications`, or `Shift+F10`: Open the command palette in supported modes
- `?`: Open help viewer
- `Read guide` button before joining: read startup instructions from the app status reader with `ArrowUp` / `ArrowDown`, `Home` / `End`, `Enter` / `Space` to repeat, and `Escape` to close
- `C`: Speak coordinates
- `Y`: Speak the room or location you are currently in
- `Escape`: With a held remote, release remote-control focus so arrow keys move again; otherwise press once for disconnect prompt, press again to disconnect

### Users, Nickname, Chat
- `L`: Locate nearest user
- `Shift+L`: List users alphabetically; `Enter` teleports to selected user; `ArrowLeft`/`ArrowRight` adjust selected user volume
- `Shift+R`: Open reactions and actions toward the selected, focused, or nearest user, including hug, focus, tap, hand, walk, teleport, and direct message options. `Enter` runs the highlighted action; `Space` lets the system pick a safe dynamic action such as announcing focus or tapping a shoulder
- Desktop clients also use `Ctrl+R` for this in-world reactions and actions menu. In the browser Web UI, `Ctrl+R` remains the normal browser refresh shortcut.
- `Shift+H`: Ask the server to allow the selected, focused, or nearest visitor into the guarded house. The owner or authorized resident must be inside that house or standing with the visitor on the exact exterior-door square; the visitor does not need an access code.
- `U`: Speak your current location, connected-user count, and connected users
- `N`: Edit nickname
- `/`: Start chat
- In chat, commands are supported when `/` is the first character:
  - `/me <action>`: Send action text without `name:`
  - `/hug [user]`, `/hi [user]`, `/self`, and `/user [name]`: Send social reactions, including self-reactions
  - `/tap <user>`, `/chat <user>`, `/cuddle [user]`, `/kiss [user]`, `/handshake [user]`, `/holdhands [user]`, `/highfive [user]`, `/fistbump [user]`, `/cheer [user]`, `/clap [user]`, `/laugh [user]`, `/smile [user]`, `/wink [user]`, `/nod [user]`, `/blush [user]`, `/cry [user]`, `/yawn [user]`, `/apologize [user]`, `/forgive [user]`, `/bow [user]`, `/dance [user]`, `/comfort [user]`, `/pat <user>`, `/poke [user]`, `/boop [user]`, `/salute [user]`, `/thumbsup [user]`, `/heart [user]`, `/sparkle [user]`, `/celebrate [user]`, `/tease <user>`, `/smack <user>`, `/whisper <user>`, and `/listen [user]`: Send more human social reactions. Physical-comedy actions such as smack are playful in-world reactions, not moderation or harm.
  - `/walkto <user>`: Move to a nearby square beside a user
  - `/teleportto <user>` or `/join <user>`: Teleport to a user's square
  - `/up`: Show server uptime (self only)
  - `/version`: Show server version (self only)
  - `/go <location>`: Travel to another location, such as `/go arcade`
- `Shift+Z`: Admin menu (when role permissions allow)
- `,` / `.`: Previous/next message; while holding a radio remote, tune connected radios to the previous/next station instead
- `<` / `>`: First/last message; while holding a radio remote, tune connected radios to the previous/next station instead
- `Ctrl+,` / `Ctrl+.`: Read previous/next message in the focused two-person direct conversation
- `Ctrl+Shift+,` / `Ctrl+Shift+.`: Move conversation focus backward/forward through online users
- `Ctrl+M`: Write to the focused two-person direct conversation
- `Ctrl+[` / `Ctrl+]`: Read previous/next public-room message
- `Ctrl+Shift+[` / `Ctrl+Shift+]`: Read previous/next system message

### Items
- `I`: Locate nearest item
- `Shift+I`: List items and teleport to selected item with `Enter`
- `A`: Add item
- `O`: Edit item properties
- `Shift+O`: Inspect all item properties
- `D`: Pick up or set down an item. Picking up movable furniture automatically carries everything resting on it as one balanced load; setting it down preserves every supported item's surface placement. Small carried objects and portable radios auto-place on an open focused surface when one is available.
- `Shift+D`: Pick up/drop the selected item with attached or linked parts. Furniture already includes its supported contents with normal `D`.
- `J`: Take the last focused grabbable item from a table, shelf, counter, or other surface. Fixed, wall-mounted, ceiling-mounted, window-mounted, and fixture items cannot be grabbed.
- `Shift+J`: Announce what is on the focused table, shelf, counter, or other surface. With no surface focused, announce loose items on the floor at the current square.
- `Tab` / `Shift+Tab`: Refocus held remote controls with `Tab`; `Shift+Tab` switches to another held item and focuses its controls. Without a held remote, cycle carried and nearby usable items. The server currently allows up to 4 carried items at once.
- `Z`: Item management menu (delete/transfer when permitted)
- `Space` in item management menu: Read tooltip/help for the selected action
- `Enter` or `Space`: Use the focused/current item, doorway, portal, chair, couch, or bed; beds support sitting, then lying down, then getting up when used again. When several items are available, selection starts on the item you last focused or used
- `Shift+Enter`: Perform the focused/current physical object interaction, such as repairing a damaged object or moving a placed object off its surface. It never picks an item up; use `J` or `D` for pickup/drop.
- First use of an unconfigured house alarm opens access enrollment. Press `1` for signed-in account access or `2` for signed-in account plus a private resident keypad code. Code entry is masked; `Enter` saves and `Escape` cancels. Only the owner or an already authorized resident can complete setup.
- After setup, using a house alarm opens its private keypad. Enter digits, `*`, or `#`; `Backspace` removes the last character; `Enter` submits without speaking the code; blank `Enter` checks the signed-in resident identity; `Escape` cancels.
- At a guarded house front door, a visitor uses the alarm keypad and presses `Enter` with no code to request entry. The resident/owner receives an in-world alert with the exact visitor name and can use `/allow <user>` or `/deny <user>` from any room inside that same protected house. The owner or authorized resident may also stand on the exact exterior-door square with the visitor and use `Shift+H` or `/allow <user>`; no access code is required. Approval keeps the visitor outside for ten seconds, then opens the door and moves them inside; denial leaves them outside.
- A resident can also configure a separate in-world guest keypad code in the house alarm properties/Admin item editor. The visitor enters that code at the alarm keypad; it grants temporary guest access after the short entry delay. Use a game-only code, not a real home-security code.
- `Shift+J`: Jump through or activate the focused/current portal-style item

### Audio
- `P`: Ping server
- `V`: Set microphone gain
- `Shift+V`: Microphone calibration
- `M`, `8`, or `Shift+8`: Mute/unmute local microphone
- `Shift+M`, `7`, or `Shift+7`: Toggle stereo/mono output
- `Shift+1` (`!`): Toggle loopback monitor
- `1`, `9`, or `Shift+9`: Toggle voice layer
- `2` or `Shift+2`: Toggle item layer (emit sounds)
- `3` or `Shift+3`: Toggle media layer (radio)
- `4` or `Shift+4`: Toggle world layer (other-user world sounds)
- `Space` / `Shift+Space` with a carried media remote: Tune connected radios or TVs forward/backward
- `ArrowRight` / `ArrowLeft` with a carried media remote: Tune connected radios or TVs forward/backward
- `ArrowUp` / `ArrowDown` with a carried media remote: Raise/lower connected radio or TV volume
- `,` / `.` with a carried media remote: Tune connected radios/speakers or TVs in the current location/group, or only the current device when linked control is off in the remote settings
- `Ctrl+ArrowLeft` / `Ctrl+ArrowRight` with a carried media remote: Tune connected radios/speakers or TVs in the current location/group, or only the current device when linked control is off
- `Ctrl+Shift+Up` / `Ctrl+Shift+Down` or `Ctrl+Shift+U` / `Ctrl+Shift+D` with a carried media remote: Raise/lower connected radio/speaker or TV volume, or only the current device volume when linked control is off
- `Home` / `End` with a carried media remote: Tune the first/last station or channel preset
- `O` with a carried media remote: Toggle connected radios or TVs on or off
- `I` with a carried media remote: Read station/channel, power, volume, and now-playing information
- `C` with focused carried media remote, or `Shift+K`: Cast an available local screen, window, tab, or media app source to a nearby TV or radio
- New radios added from the item menu start with the Town Square station presets, including Tony Gebhard Radio
- `5` or `Shift+5`: Cycle TTS announcements between full, alert sounds only, and required only
- `6` or `Shift+6`: Toggle optional nearby item beacons
- `E`: Effect select menu
- `-` / `=`: Lower/raise master volume
- `_` / `+` (`Shift+-` / `Shift+=`): Lower/raise active effect value

## Text Entry Modes (`nickname`, `chat`, `alarmSetupMethod`, `alarmSetupCode`, `alarmKeypad`, `itemPropertyEdit`)

- `Enter`: Confirm
- `Escape`: Cancel
- `ArrowLeft` / `ArrowRight`: Move cursor by character
- `Ctrl+ArrowLeft` / `Ctrl+ArrowRight`: Move cursor by word (notepad-style)
- `Home` / `End`: Move to start/end
- `Backspace`: Delete previous character
- `Delete`: Delete current character
- `Ctrl+A`: Select all (replace-on-next-type)
- `Ctrl+C`: Copy current text
- `Ctrl+X`: Cut current text
- `Ctrl+V`: Paste
- `Cmd+A` / `Cmd+C` / `Cmd+X` / `Cmd+V` (macOS): same behavior as `Ctrl` shortcuts above

## Numeric Edit Fields

- `ArrowUp` / `ArrowDown`: Step value
- `PageUp` / `PageDown`: Step by 10 increments

## Menu/List Navigation Modes

Applies to effect select, user/item list modes, item selection, item property list, and property option select.

- `ArrowUp` / `ArrowDown`: Move selection
- `PageUp` / `PageDown` in item property list: Jump 10 values for left/right-editable option fields
- `PageUp` / `PageDown` in item property option select: Jump 10 options backward/forward
- `ArrowLeft` / `ArrowRight` in user list: Lower/raise selected user listen volume (`0.5..4.0`)
- `Enter`: Confirm selection
- `Escape`: Exit/cancel
- `Space`: Read tooltip/help for current option (where metadata is available)
- First-letter navigation: jump to next matching entry
- Location list mode opens with `G`, `Ctrl+G`, or `Shift+G`; `Enter` travels to the selected location.
- Movement, portals, location travel, and nearby user movement are announced as short room-style narration so the grid can be followed like interactive fiction.

## Command Palette

- Available in `normal` mode and `pianoUse` mode
- Opens with `Shift+K`, `Applications`, or `Shift+F10`
- Shows only commands available in the current mode/context
- `ArrowUp` / `ArrowDown`: Move selection
- `Enter`: Run selected command
- `Escape`: Close palette and return to prior mode
- `Space`: Read tooltip/help for selected command
- First-letter navigation: jump to next matching command

## Yes/No Confirmation Menu

- `ArrowUp` / `ArrowDown`: Move between `No` and `Yes`
- `Enter`: Confirm current choice (default selection is `No`)
- `Escape`: Cancel

## Admin Modes

- `Shift+Z`: Open admin menu
- `Space` on admin root actions: Read tooltip/help for the selected action
- Admin menu options are permission-gated and include:
  - platform overview for server/client version, connected users, item count, and seeded platform links
  - owned content for signed-in creators to list their own items and grid locations
  - role management
  - change user role
  - ban user
  - unban user
  - delete account
- In admin role management:
  - role list includes role user-counts
  - `Enter` on role opens permission toggles
  - `Enter` on `Add role` opens role name editor
  - role delete prompts replacement role selection

## Piano Use Mode

- Opening a piano item automatically requests MIDI access when the browser allows it; the `Enable MIDI` button appears there as the manual fallback.
- Physical MIDI note-on/note-off plays the active piano item directly and broadcasts the notes through the piano item.
- Piano-style instruments use the 88-key A0-C8 MIDI range.
- `1-9` (and `0` for the 10th slot): Switch instrument preset quickly
- `A S D F G H J K L ; '`: Play white keys (C major from C4 upward)
- `W E T Y U O P ]`: Play sharps
- Multiple keys can be held/played at once
- Shifted note keys are ignored
- `?`: Open piano-mode help viewer
- `-` / `=`: Shift octave down/up
- `Z`: Start, pause, or resume recording on this piano (max 30s recorded time)
- `X`: Play back saved recording on this piano (stops demo first)
- `Enter`: Play demo melody (press again to restart; stops recording playback first)
- `C`: Stop demo, recording playback, and active recording
- `Escape`: Exit piano mode

## Help Viewer Mode

- `ArrowUp` / `ArrowDown`: Previous/next help line
- `Home` / `End`: First/last help line
- `Escape`: Exit help viewer
- No first-letter navigation in this mode
# Location ambience administration

Open the Admin menu and choose **Location ambience**. Choose a world location,
then use the normal list keys to browse the full FX ambience library. Press
Space for the original source filename, duration, seam crossfade, and loop
points. Press Enter to assign the highlighted loop. Escape returns first to
the location list and then to the Admin menu.
