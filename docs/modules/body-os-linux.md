# body/crates/os_linux (the Linux OS backends)

**Purpose.** The Linux implementations of the body's OS-capability ports: notifications over the
freedesktop D-Bus service, volume through `pactl`, screen capture from the X root window or through
the desktop portal's `Screenshot` call, and the global hotkey as an X key grab, through
`kglobalaccel` on KDE Plasma, or through the portal's `GlobalShortcuts` calls, and a pasted
picture from the X clipboard or the Wayland one. What every
platform crate shares (the public contract, the coverage exemption, the invariants and the
dependencies) is in [body-os.md](body-os.md).

## The backends

Each is a covered core over a port of its own, an adapter tested against a peer the test
controls, and a session step taken by the caller ([ADR-0011](../adr/ADR-0011-body-v1.md)
decision 13).

- **`LinuxNotify<B: NotificationBus>`** asks the freedesktop notification server for its
  capabilities, then sends one `Notify` call attributed to the app name it was built with. The
  summary is the title as plain text, which is all the specification allows there. The body is the
  message, escaped with `escape_xml` only when the server lists `body-markup`, and for a tainted
  reminder the fixed provenance line after a newline; the inert-text rule removes every newline
  from the message, so that line cannot be forged. `ServiceUnknown`, `NameHasNoOwner` or
  `NoServer` is `NotifyError::Unavailable`, anything else `Backend`. An accepted call returns
  `Ok(true)`, because the specification gives a server no way to decline.
- **`DbusNotifications`** makes those two calls on a `zbus::blocking::Connection` it is given. The
  crate re-exports `zbus`, and the host opens the session bus with
  `zbus::blocking::Connection::session()`. When that fails, `DbusNotifications::absent(&error)`
  stands in for the bus, and each call fails with the error's text under the name `NoServer`.
- **`LinuxAudioControl<R: PactlRunner>`** reads and changes `@DEFAULT_SINK@` through `pactl`, so
  it works against PulseAudio and against PipeWire's `pipewire-pulse`. The level is the mean of the
  channels' raw volumes over `PA_VOLUME_NORM` (65536), clamped to `[0, 1]` because a server allows
  a boost past 100%, and a set writes the raw integer. Stderr naming `No such entity` (no sink) or
  `Connection failure` (no server) is `AudioError::NoEndpoint`; any other failure, including a
  missing `pactl`, is `Backend`.
- **`PactlCommand`** starts the program (`PACTL_PROGRAM`, `pactl` on `PATH`) with `LC_ALL=C`, so
  the output it parses is never translated.
- **Screen capture**, from the X root window or through the desktop portal's `Screenshot` and
  `ScreenCast` calls, and the overlay kept out of it, is in
  [body-os-linux-capture.md](body-os-linux-capture.md).
- **`LinuxHotkey`** resolves a chord to the X keysym of its `KeyboardEvent.code` (`keysym`: a
  letter is its lower-case keysym, `F1` to `F35` are `ffbe` to `ffe0`, the named keys are their
  keysyms), finds the lowest keycode that types it, and takes Shift and Control from the core
  protocol's fixed bits and Alt, Super and Num Lock from whichever modifier holds `Alt_L` or
  `Alt_R`, `Super_L` or `Super_R`, and `Num_Lock`. A passive grab matches the modifier state
  exactly, so it grabs the key with each combination of Caps Lock and Num Lock added. A key the
  keyboard lacks, or Alt or Super on no modifier, fails as `Registration` before any grab; a
  refused grab, such as `BadAccess` when another client holds the chord, fails it at that variant.
  The first successful registration starts one thread that reads key events until the connection
  fails and runs each binding whose keycode matches and whose state, without the pointer buttons
  and the two locks, equals its modifiers. It skips a press with the keycode and time of the
  release just before it, which is how the server sends each auto-repeat, so a held chord runs
  once, as on Windows, where `global-hotkey` registers with `MOD_NOREPEAT`. A failed registration
  starts no thread, so dropping the backend closes the connection and the server releases any
  variant it did grab.
- **`X11Keys`** reads the keyboard with `GetKeyboardMapping` over every keycode the setup lists and
  `GetModifierMapping`, grabs with `GrabKey` on the root of its screen (no owner events,
  asynchronous pointer and keyboard) checked for an error before it returns, and reads events until
  a `KeyPress` or `KeyRelease`. The host opens the display with `x11rb::connect(None)` as for
  capture, and `X11Keys::absent(&error)` fails every request with the error's text. On a Wayland
  session an X grab is assumed to see keys only while an X window has focus, so a Wayland session
  needs the portal backend below.
- **`LinuxPortalHotkey`** registers a chord through `org.freedesktop.portal.GlobalShortcuts`
  (version 1). Each registration creates its own session (`CreateSession` with `handle_token` and
  `session_handle_token`), then binds one shortcut in it (`BindShortcuts`): the id is the chord's
  text, such as `ctrl+alt+space`, so a trigger the user changed in the compositor is kept per
  chord; the description is the one the backend was built with; the preferred trigger is the chord
  in the XDG shortcuts form (`trigger`: `CTRL`, `ALT`, `SHIFT` and `LOGO`, then the key's xkb
  keysym name from `keysym_name`, such as `space`, `Return` or `F5`). A response must have code 0
  and name the computed session handle, then the shortcut id; code 1 (cancelled), any other code,
  or a success without the name fails as `Registration` and binds or keeps nothing. Request and
  session handles come from the unique bus name as for `Screenshot`, with a fresh token
  `cortex<n>` per request. The first successful registration starts one thread that reads
  `Activated` and `Deactivated` signals and passes each to the `Hold` of the binding whose
  session and id it names; the binding runs when its `Hold` counts the signal as a press.
- **A held chord runs once**, as on X11 and Windows. A backend may send one `Activated` per
  auto-repeat, as the KDE one does, then one `Deactivated` at the release
  ([globalshortcuts-portal](../readings/globalshortcuts-portal.md)). `Hold` counts an `Activated`
  as a press when it is the first after a `Deactivated`, or comes `REPEAT_GAP` (1 s) or more after
  the binding's last `Activated`, by the listener's clock; the gap serves a backend that sends no
  `Deactivated` or loses one. It is above `kwin_wayland`'s default 600 ms repeat delay; a longer
  delay runs a held chord again at its first repeat.
- **`DbusShortcuts`** makes those calls through the same request module as `DbusPortal`: the
  `Response` match before the call, the returned handle checked, only a `Response` from the
  connection that sent the method reply read, and the reply and the `Response` waited for under
  one limit, `SHORTCUTS_LIMIT` (1 min), since a compositor may first ask the user
  to confirm or change the trigger. It subscribes to every `GlobalShortcuts` signal on the
  portal's path when it is built, so a press between a bind and the first read is kept and a
  `Deactivated` is never read before its `Activated`, and skips any other signal, such as
  `ShortcutsChanged`. Any process on the bus can send those signals, so it reads one only from
  the unique name the bus gives for `org.freedesktop.portal.Desktop` (`GetNameOwner`, asked at
  the first signal and kept once named), and skips one whose arguments do not parse; only a
  failed connection ends the listener. It reads the session handle as a string, which the 1.18
  frontend sends, or as an object path, and the bound ids from the `shortcuts` result. The tests
  run the check list over the core with a fake, and the adapter against a fake portal over a
  socket pair. Each test that starts the listener then closes the bus and waits for it to return,
  since llvm-cov miscounts a loop that a thread is still in when the test binary exits
  ([rust-coverage-toolchain](../readings/rust-coverage-toolchain.md)). No live test exists
  ([788](../refinements/tasks/788-test-the-portal-hotkey-on-a-kde-wayland-session.md)): the one
  backend here, `xdg-desktop-portal-kde` 5.27.11, binds nothing through the 1.18 frontend and
  runs `xdg-open` on System Settings' shortcuts page at each `BindShortcuts`
  ([globalshortcuts-portal](../readings/globalshortcuts-portal.md)).
- **`LinuxKdeHotkey`** registers each chord with `org.kde.kglobalaccel`, which KWin runs on Plasma,
  as an action of the fixed component `cortex` named by the chord's text, so a restart registers
  the same action, with the chord as a Qt key code (`qt_key`, `qt_code`: `0x0C00_0020` for
  Ctrl+Alt+Space, the one chord run live). A reply without the key (0 when another action holds
  it) fails as `Registration` and removes the action. Signals go to each binding's `Hold` as
  above. Dropping the backend removes its actions, which `kglobalaccel` keeps grabbed with no
  client; a run that ends without the drop leaves them, and the next run takes the key back.
- **`DbusGlobalAccel`** calls `doRegister`, `setShortcut` with flags 6 (`NoAutoloading`: the chord
  given replaces a key a past run kept; `SetPresent`: it is grabbed now) and `unregister`, and
  reads `globalShortcutPressed` and `globalShortcutReleased` on `/component/cortex` only from the
  owner of `org.kde.kglobalaccel`, which `kglobalaccel_running` asks for. Tested as the portal is.
- **`LinuxClipboardPicture<S: SelectionRead>`** reads the owner's list of types, then asks for
  `image/png`, `image/jpeg` and `image/webp` in that order, only those listed, each with the
  `MAX_PASTED_BYTES` limit, and returns the first non-empty answer with its type. A request the
  owner was silent on is sent once more, as `xclip` drops one that arrives while it sends the
  webview a large picture; an owner that answers every type with its data, as `xclip` does, is
  asked only for what it lists. `SelectionError::Over` is `ClipboardError::TooLarge`, a second
  silence or `Failed` is `Failed`, and each ends the read at once.
- **`read_dropped_file(path, limit)`** reads a native drop's file for `dropped_pictures`: at most
  `limit` bytes of a regular file of at most `limit` bytes, else `None`, so a directory, a device
  or a missing path is never read.
- **`X11Selection`** lists the types by converting to `TARGETS` (at most 4096 bytes) and asking
  the server for each atom's name. It converts the `CLIPBOARD` selection to one type through an
  unmapped `InputOnly` window of its own that watches property changes: `ConvertSelection` into
  `CORTEX_PASTE`, then a `GetProperty` that deletes it, asking for one word more than the limit
  allows. An `INCR` answer is read chunk by chunk on each new value until an empty one, failing as
  `Over` past the limit. A `SelectionNotify` naming no property is `None`. Each wait for the owner
  lasts at most `SELECTION_LIMIT` (1 s), after which the read is `Silent`, and the window is
  destroyed after every read. Tested against a fake X server as `X11Keys` is.
- **`WaylandSelection`** binds the first `wl_seat` and gets its data control device from
  `ext_data_control_manager_v1` where the compositor lists it, else from
  `zwlr_data_control_manager_v1`, then makes a round trip, after which the compositor has sent
  the current selection's offer and its types. A read with neither manager or no seat is `Failed`
  with that reason, and no selection lists nothing and converts to `None`. A conversion sends
  `receive` with the write end of a pipe, closes its own copy, makes a round trip so the
  compositor has passed the pipe on, and reads the pipe to its end, `Over` past the limit. A wait
  of `SELECTION_LIMIT` with no new bytes is `Silent`, and so is a failed wait or read on the pipe.
  Each read binds new objects, which go with the connection, so the caller connects once per
  paste. Tested against a fake compositor (`wayland-server` over a socket pair) serving either
  protocol. The shell does not use it yet: it reads through `X11Selection` only.
- **The shell** grabs through `X11Keys` unless `WAYLAND_DISPLAY` is set and not empty. Then, on a
  thread and bus connection of its own, since a portal bind can wait `SHORTCUTS_LIMIT` on the user,
  it keeps a `LinuxKdeHotkey` for the run whenever `kglobalaccel_running`, before any portal call,
  since a failed portal bind on Plasma 5.27 has already opened the settings page, else it uses
  `LinuxPortalHotkey`. Both show the user "Show or hide the Cortex overlay".
- `just os-linux-live` runs the five `#[ignore]`d live tests: a notification shown on the session
  bus, a volume and mute round trip on the default sink that restores what it found, a capture on
  `DISPLAY` that is refused before the test maps a window naming its own process and, after, comes
  back with that window black and a white window of no process around it still white, a window
  capture that is `NoTarget` over a desktop window and its own, then names the topmost titled window
  not its own or a dock, and a `ctrl+alt+space` grab that XTEST presses with Num Lock off and on and
  holds for 1.5 s, each of which must run the callback once, and that `ctrl+space` must not run.
- `cargo test -p os-linux --test portal_live -- --ignored --nocapture` runs the portal's live test
  on a session bus whose portal serves `Screenshot`: two display captures of the same size, and
  each file the backend read gone afterwards; `--test accel_live` waits on a KDE session bus for a
  tap, a hold and a tap of `ctrl+alt+space`, which must run the callback three times; and
  `--test screencast_live` needs a `ScreenCast` portal with a window source and `gst-launch-1.0`
  on `PATH`. Its first focus capture must be `NoTarget` with `NO_WINDOW`, the hide it then reports
  opens the chooser, and once a person picks a window, a later capture must be that window read
  alone, with no display size. All three are outside `just os-linux-live`, which needs an X server
  ([wayland-screencast-portal](../readings/wayland-screencast-portal.md) has the headless KWin run).
