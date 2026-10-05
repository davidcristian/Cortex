# body/crates/os_linux (the Linux OS backends)

**Purpose.** The Linux implementations of the body's OS-capability ports: notifications over the
freedesktop D-Bus service, volume through `pactl`, screen capture from the X root window or through
the desktop portal's `Screenshot` call, and the global hotkey as an X key grab, through
`kglobalaccel` on KDE Plasma, or through the portal's `GlobalShortcuts` calls. What every
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
- **`LinuxScreenCapture<G: RootGrab>`** reads one monitor of the root window and returns it as a
  display frame. It asks the port for the layout, then reads the monitor RandR marks primary, else
  the first one it lists, else the whole root. The display target promises one display (ADR-0029
  decision 16), so no fallback reads the union of several; the first listed stands in because a
  session that never ran `xrandr --primary`, Xvfb among them, marks none, and a server with no
  RandR has only the core protocol's one display per screen. It accepts one pixel layout, depth 24
  or 32 at 32 bits per pixel with the masks `ff0000`, `ff00` and `ff`, reverses each pixel when
  the server stores the most significant byte first, and refuses any other layout as `Backend`.
  No server is `NoDisplay`, and a failed layout or read is `Backend`.
- **A window target** is picked by `focus` from the same read: the topmost viewable top-level
  window, not `InputOnly` or override-redirect (menus, tooltips), with a non-empty `WM_NAME` on it
  or a window under it (a frame has none, its client has one), and no window under it of this
  process or whose `_NET_WM_WINDOW_TYPE` lists the dock type (a panel on top) or the desktop type.
  Its rectangle, with frame and border, is measured from the monitor's corner; none is `NoTarget`.
- **The overlay is kept out by its process id** (ADR-0029 decision 10). X11 has no
  `WDA_EXCLUDEFROMCAPTURE`, so `LinuxScreenCapture::new(root, process)` paints black, border
  included, every viewable window whose `_NET_WM_PID` is `process`, placed by summing its
  ancestors' offsets. GTK writes that property on each window it creates directly under the root:
  under `Xvfb` it was on the overlay and on the override-redirect context menu, and missing only
  from GTK's 1 by 1 child windows. The walk covers the whole tree, so a window manager's frame
  between the root and the overlay does not hide it. The capture is refused as `Backend` when no
  window in the tree names `process`, since the property is then not being written, and when a
  window's parent is not listed before it. The shell passes `std::process::id()`.
- **Under a compositing manager the root is not read.** Its picture is the manager's own copy of
  each window, so a fade after a hide keeps the overlay on screen while the tree lists it unmapped,
  and its shadow lies outside the overlay's rectangle
  ([x11-overlay-capture](../readings/x11-overlay-capture.md)). When the screen's `_NET_WM_CM_S`
  selection has an owner, `pieces` lists the part inside the monitor of each viewable top-level
  window that is not `InputOnly`, bottom to top, and the port returns each part read from the
  window itself. `compose` paints them bottom up over black, so no fade, shadow or other manager
  output reaches the picture, and the body's windows are then painted black as above. A window
  read is clipped to the monitor, because an off-screen part of a window the manager does not
  redirect fails with `BadMatch`. Each part is converted in its own depth and visual by the same
  rule as the root, and the alpha of a depth-32 window is dropped, so it is painted opaque. A
  top-level window's border is not read.
- **The root background is the bottom layer.** When the root's `_XROOTPMAP_ID` names a pixmap at
  the root's depth, as feh and similar setters write it, the port reads the part of it inside the
  monitor, from the root's corner and not tiled, as picom paints it, and describes that read by
  the root visual, since a pixmap's `GetImage` reply names visual 0. With no property, a pixmap of
  another depth, a pixmap the server no longer has, or none of it on the monitor, the base stays
  black and the capture goes on. picom paints black where it has no background, so the capture
  matches its screen; xcompmgr tiles a small pixmap and paints gray where there is none, so there
  the capture differs ([x11-overlay-capture](../readings/x11-overlay-capture.md)). `xsetroot
  -solid` writes no property, so neither manager nor the capture shows its colour.
- **`X11Root`** lists the active monitors with RandR 1.5's `GetMonitors`, which reports each
  monitor's primary flag and rectangle in one request; a server without the extension lists none,
  and an X error to the request fails the capture as `Backend`. It then sends `GrabServer` on one
  screen of an `x11rb::rust_connection::RustConnection` it is given, lists the window tree a level
  at a time with `QueryTree`, `GetWindowAttributes`, `GetGeometry` and a `GetProperty` each of
  `_NET_WM_PID` (`CARDINAL`), `WM_NAME` (zero length, which tells a titled window) and
  `_NET_WM_WINDOW_TYPE` (`ATOM`) per window, and asks `GetSelectionOwner` of `_NET_WM_CM_S` and the
  screen's number. With no owner it sends one `GetImage` (`ZPixmap`, every plane) for the chosen
  rectangle of the root, and returns `Pixels::Root`. With an owner it sends a `PIXMAP` `GetProperty`
  of `_XROOTPMAP_ID` on the root, `GetGeometry` and `GetImage` of the pixmap named, then one
  `GetImage` per part `pieces` lists, on the window itself, and returns `Pixels::Layers`, so the
  root's own pixels are never read there. It then sends and flushes `UngrabServer`, also after a
  failed read. No other client can map, move or draw a window between the reads and the list. It
  reads the bits per pixel, byte order and visual masks of each read from the connection's setup.
  The crate re-exports `x11rb`, and the host opens the display with `x11rb::connect(None)`. When
  that fails, as on a Wayland session with no `DISPLAY`, `X11Root::absent(&error)` makes every read
  `NoDisplay`. Rootless Xwayland, such as WSLg's, answers `GetImage` on its root with `BadMatch`, so
  the read fails as `Backend` rather than returning a partial picture; a Wayland session needs the
  desktop portal instead.
- **`LinuxPortalCapture<P: ScreenshotPortal>`** captures a Wayland session through
  `org.freedesktop.portal.Screenshot`. It builds the request handle
  `/org/freedesktop/portal/desktop/request/<sender>/<token>` from the port's unique bus name,
  without its `:` and with each `.` as `_`, and a token `cortex<n>` from a counter. It asks for a
  non-interactive screenshot and reads the `Response`: code 0 with a `uri` is a picture; 0 without
  one, 1 (cancelled) and any other code fail as `Backend`. The `uri` must be `file://` with an empty
  host, and its `%XX` escapes are decoded. It reads the file, removes it, then decodes it. A focus
  target is `NoTarget` before any call, because a portal picture does not say where any window is,
  so this backend does not run the shared screen list, whose focus checks need one. One capture
  runs at a time, since the wlr backend writes every picture to the same `/tmp/out.png`.
- **The picture file is removed after it is read**, whether or not it decodes, and a failed removal
  fails the capture as `Backend`, so the body never sends a picture whose copy it left on disk. The
  wlr backend's file is the whole screen, in `/tmp`, mode 664 under a 002 umask
  ([wayland-screenshot-portal](../readings/wayland-screenshot-portal.md)), and the user did not ask
  to keep it.
- **`decode_png`** lives here rather than in `body_core`, which only encodes, because this backend
  is the one that reads a PNG; it uses the `png` crate `body_core` already depends on. It expands
  palette and 16-bit pictures to 8-bit channels, accepts RGB and RGBA, refuses grey, and writes
  BGRA with a fourth byte of 255. A header whose decoded size is over `MAX_DECODED_BYTES` (256
  MiB) is refused before the buffer is made.
- **`DbusPortal`** adds a match rule for `Response` on the handle before it calls `Screenshot("",
  {handle_token, interactive: false})` on `org.freedesktop.portal.Desktop`, because a backend can
  answer before the method reply arrives. A returned handle other than the computed one fails,
  since no `Response` would come on it, and a `uri` that is not a string counts as none. It reads
  and removes the file with `std::fs`. The host opens the session bus as for notifications, and
  `DbusPortal::absent(&error)` fails each portal call with the error's text.
- **The wait for the method reply and then the `Response` ends at one limit**, counted from the
  call: `RESPONSE_LIMIT` (10 s) for `DbusPortal::new`, or the `limit` given to
  `DbusPortal::with_limit`. `Connection::session()` sets no method timeout, so the reply is raced
  against the same deadline as the `Response`. A portal that never answers, such as one whose
  permission dialog nobody closes or a frontend that never replies, would otherwise hold the
  blocking thread the `BodyService` server gave the call and, through the capture lock, every
  later capture. The value is the
  default of the brain's `CORTEX_BODY_CAPTURE_TIMEOUT_S`, after which no caller waits for the
  picture, and several hundred times the median `Response` time measured on headless sway
  ([wayland-screenshot-portal](../readings/wayland-screenshot-portal.md)). At the limit the call
  fails as `Backend`, naming the reply or the `Response` as the message that did not come, the
  `Response` match is dropped, and `Close` is sent to the request with no
  reply awaited, so the portal ends any dialog and sends no late answer. A file the backend wrote
  before the `Close` stays; the wlr backend's fixed path is overwritten and removed by the next
  capture.
- **`HiddenOverlayCapture<S: ScreenCapture>`** keeps the overlay out of a picture that cannot
  leave a window out, which a portal picture cannot (ADR-0029 decision 10). The shell reports each
  show of the overlay to an `OverlayWatch` before showing it, and each hide only after the hide
  succeeded. A capture is refused as `Backend` while the overlay is shown and until `settle` has
  passed since the last hide, before the inner capture runs; a picture is discarded the same way
  when a show was recorded while it was being taken, so a summon during the call cannot reach the
  brain. The shell passes `OVERLAY_SETTLE` (1 s), about three times picom's default fade
  (`fade-out-step` 0.03 every `fade-delta` 10 ms, read from its defaults, not run). The shell
  never hides the overlay to take a picture: a compositing manager's fade kept a hidden overlay in
  the picture ([x11-overlay-capture](../readings/x11-overlay-capture.md)), a Wayland compositor
  always composites, and no protocol tells a client when its hidden window has left the screen. A
  fade set longer than the settle time is the accepted risk.
- **The shell picks the portal when `WAYLAND_DISPLAY` is set and not empty**, the variable a
  Wayland client connects by and GTK chooses its backend by, and the one the hotkey uses.
  `XDG_SESSION_TYPE` describes the login, not the display: it read `tty` in the headless sway run
  that served the portal. There is no X11 fallback through Xwayland, since rootless Xwayland
  answers a root `GetImage` with `BadMatch`. It opens one session bus for notifications and the
  portal, serves `LinuxPortalCapture` over `DbusPortal` inside `HiddenOverlayCapture`, and still
  needs `CORTEX_HOST_CAPTURE=1`. A Wayland capture is refused while the overlay is open, which is
  most of a turn, so it reads the screen when the user hides the overlay before the model asks.
  A `ScreenCast` window source would leave the overlay out: `xdg-desktop-portal-wlr` 0.7.1 offers
  none, and `xdg-desktop-portal-kde` 5.27.11 does, designed in [ADR-0073](../adr/ADR-0073-wayland-window-capture.md)
  ([wayland-screencast-portal](../readings/wayland-screencast-portal.md),
  [787](../refinements/tasks/787-read-a-wayland-window-through-the-screencast-portal.md)).
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
  `Response` match before the call, the returned handle checked, and the reply and the `Response`
  waited for under one limit, `SHORTCUTS_LIMIT` (1 min), since a compositor may first ask the user
  to confirm or change the trigger. It subscribes to every `GlobalShortcuts` signal on the
  portal's path when it is built, so a press between a bind and the first read is kept and a
  `Deactivated` is never read before its `Activated`, and skips any other signal, such as
  `ShortcutsChanged`. Any process on the bus can send those signals, so it reads one only from
  the unique name the bus gives for `org.freedesktop.portal.Desktop` (`GetNameOwner`, asked at
  the first signal and kept once named), and skips one whose arguments do not parse; only a
  failed connection ends the listener. It reads the session handle as a string, which the 1.18
  frontend sends, or as an object path, and the bound ids from the `shortcuts` result. The tests
  run the check list over the core with a fake, and the adapter against a fake portal over a
  socket pair. No live test exists
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
  tap, a hold and a tap of `ctrl+alt+space`, which must run the callback three times. Both are
  outside `just os-linux-live`, which needs an X server.
