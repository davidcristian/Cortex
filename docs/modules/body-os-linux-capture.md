# body/crates/os_linux: screen capture (the Linux capture backends)

**Purpose.** The `ScreenCapture` backends of the Linux crate: the X root window, the desktop
portal's `Screenshot` call, a window read through its `ScreenCast` calls with the chooser opened
at the overlay's hides, the router between the last two, and the wrapper that keeps the overlay out
of a picture that cannot leave it out. The crate's other
backends and its live tests are in [body-os-linux.md](body-os-linux.md), and what every platform
crate shares is in [body-os.md](body-os.md).

## The backends

Each is a covered core over a port of its own, an adapter tested against a peer the test
controls, and a session step taken by the caller ([ADR-0011](../adr/ADR-0011-body-v1.md)
decision 13).

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
- **The request module reads only the `Response` the replying portal sent.** Any process on the
  session bus can send a `Response` on a handle, and a forged `uri` would make the backend read and
  remove a file of the sender's choosing. The bus sends the call to the owner of
  `org.freedesktop.portal.Desktop` and passes a reply only from that connection, so the module
  reads only a `Response` whose sender is the method reply's, and fails a reply with no sender.
  It asks the bus for no owner first: the call itself starts a portal that is not running yet,
  which a `GetNameOwner` before the call would find with none. The `uri`'s directory is not
  checked, since the frontend passes on whatever path the backend wrote, and the wlr backend
  writes `/tmp/out.png` ([wayland-screenshot-portal](../readings/wayland-screenshot-portal.md)).
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
  portals, and still needs `CORTEX_HOST_CAPTURE=1`. A display capture is `LinuxPortalCapture`
  over `DbusPortal` inside `HiddenOverlayCapture`, refused while the overlay is open, which is most
  of a turn, so it reads the screen when the user hides the overlay before the model asks.
- **The shell asks `offers_window` once**, in `serve_wayland` of
  `body/app/src-tauri/src/body_server.rs`, on a blocking task so that setup does not wait on the
  bus. When the `ScreenCast` portal offers a window source, as `xdg-desktop-portal-kde` 5.27.11
  does, it serves a `TargetRouter` that sends a focus request to the `LinuxWindowCapture` over
  `DbusScreenCast` and `GstLaunch::new(GST_LAUNCH_PROGRAM, FRAME_LIMIT)`, watching the
  `OverlayWatch` with `CHOOSER_LIMIT`, and a display request to the capture above. Otherwise, as
  under `xdg-desktop-portal-wlr` 0.7.1, which offers none, it serves the display capture alone,
  logging the error when the property could not be read
  ([wayland-screencast-portal](../readings/wayland-screencast-portal.md),
  [787](../refinements/tasks/787-read-a-wayland-window-through-the-screencast-portal.md)).
- **`TargetRouter<F, D>`** sends a `CAPTURE_TARGET_FOCUS` request to `F` and a
  `CAPTURE_TARGET_DISPLAY` request to `D`, and does nothing else.
- **`LinuxWindowCapture<P: ScreenCastPortal, R: FrameReader>`** is the core of the Wayland window
  capture of [ADR-0073](../adr/ADR-0073-wayland-window-capture.md). It answers a focus request; a display request is `Backend` before any call. It keeps the portal's
  last `restore_token` in a `Mutex<Option<String>>`, held for the whole capture, since a token
  starts one session only. With no token a focus capture makes no call, records that a choice is
  wanted (`choice_wanted`), and is `NoTarget` with the fixed `NO_WINDOW` message. With one it asks
  the port for a session restored from it, waiting at most `RESTORE_LIMIT` (2 s). A stream's new
  token replaces the old one, and a stream with none leaves no window chosen. `FrameReader::read`
  takes the `OpenPipeWireRemote` descriptor and the node and returns PNG bytes, `Close` is sent on
  the session whether or not the read worked, and `decode_png` makes the bytes a
  `CapturedFrame::window_only`.
- **A restored session that does not start** is closed, its token forgotten and a choice wanted:
  past the limit or on `CANCELLED` (1) the capture is `NoTarget` with `NO_WINDOW`, and any other
  nonzero response code is `Backend` naming the code, then `NO_WINDOW`. A port error before
  `Start` ends is `Backend` and keeps the token.
- **`choose(limit)`** clears the wanted flag, opens a session with no token, so the portal shows
  its chooser, sends `Close` whatever the answer, and keeps the token only from a stream that has
  one, returning whether it kept one. Keeping one clears the flag again, since a focus capture
  refused while the chooser was open wanted the window just kept. `offers_window` reads bit 2
  (`WINDOW_SOURCE`) of `AvailableSourceTypes`.
- **`watch_hides(signal, limit)`** wraps the capture in a `WatchedWindowCapture` and starts one
  thread that waits on the `HideSignal` port, which `OverlayWatch` implements: `next_hide(seen,
  stop)` returns the hide count once the overlay is hidden with a count other than `seen`, so hides
  in quick succession are read as one, and a show after the hide waits for the next one. At each
  such hide, while `choice_wanted` is set, the thread calls `choose(limit)`; the shell passes
  `CHOOSER_LIMIT` (1 min). One thread opens one chooser at a time; a hide recorded while a chooser
  is open is read when it closes, and opens another only if a capture wanted one since. A chooser
  whose call failed keeps nothing, as a cancelled one does. Dropping the `WatchedWindowCapture`
  sets `stop` and calls `wake`, so the thread ends once any open chooser has closed; it is not
  joined, and a Rust process does not wait for its threads at exit.
- **`GstLaunch`** is the `FrameReader` adapter. It starts the program (`GST_LAUNCH_PROGRAM`,
  `gst-launch-1.0` on `PATH`) with the pipeline of ADR-0073 decision 4 for the node, `LC_ALL=C`,
  the descriptor as standard input, and both output pipes read on threads of their own. It kills
  the child once `FRAME_LIMIT` (5 s) has passed. A program that cannot start, a nonzero exit (with
  its standard error), the limit, or an output that does not begin with the PNG signature is a
  `FrameError`, which the core returns as `Backend`. It is tested with a shell script in place of
  the program.
- **`DbusScreenCast`** is the `ScreenCastPortal` adapter, over the request module `DbusPortal` uses.
  `start` builds the session handle `/org/freedesktop/portal/desktop/session/<sender>/cortexcast<n>`
  and a request token per call (`cortexcast<n>_create`, `_select`, `_start`), a prefix of its own
  because `DbusShortcuts` numbers `cortex<n>` tokens and may share the connection. It calls
  `CreateSession`, `SelectSources` with `types` 2, `multiple` false, `cursor_mode` 1,
  `persist_mode` 1 and the `restore_token` when one is given, `Start` with no parent window, and
  `OpenPipeWireRemote`, whose reply is the descriptor; `zbus` passes descriptors over its Unix
  socket with no added feature. One deadline, `limit` after the start, bounds every reply and
  `Response`. A nonzero `Start` is `Started::Refused` and an unanswered one `Started::Expired`,
  both left for the core to close. A nonzero code before `Start`, a failed call, a `Start` listing
  no stream, or no descriptor by the deadline fails, and the adapter sends `Close` on the session
  itself. `close` sends the session's `Close` with no reply awaited. `source_types` reads
  `AvailableSourceTypes` through `Properties.Get`, raced against `RESPONSE_LIMIT` or the
  `with_limit` value, and `absent` fails each call with the bus error's text. It is tested against
  a fake portal over a socket pair that sends a forged `Response` before each `Start` answer.
