# body/crates/os_* (per-platform OS backends)

**Purpose.** The adapter side of the body's OS-capability ports (ADR-0011): each crate implements
the `body_core::os` traits for one platform. The ports and the logic every platform shares live in
`body_core` ([body-core.md](body-core.md) and [body-core-capture.md](body-core-capture.md)); these
crates translate to OS calls, and `os_linux` also holds the covered logic of the protocols it
speaks. They are also where the **stub coverage exemption** is used.

- **`os_windows`** (`cfg(windows)`) is the real backend. `WindowsHotkey` wraps the `global-hotkey`
  crate, which is what keeps `unsafe_code = forbid` outside the four modules named below.
  `WindowsAudioControl` is Core Audio (`IMMDeviceEnumerator` to `IAudioEndpointVolume`).
  `WindowsNotify` is a WinRT toast (`ToastNotificationManager` to `ToastNotifier`, rendering the
  `ToastGeneric` template); `WindowsNotify::new(app_id)` takes the `AppUserModelID` the toast is
  attributed to, which an unpackaged app must own a Start Menu shortcut for (`CORTEX_TOAST_APP_ID`
  at the shell; [docs/runbooks/scheduling.md](../runbooks/scheduling.md)). `WindowsScreenCapture` is
  a GDI `BitBlt` of the primary display (`GetDC`, `CreateCompatibleDC`, `CreateCompatibleBitmap`,
  `SelectObject`, `BitBlt` with `SRCCOPY | CAPTUREBLT`, then `GetDIBits` with a **negative** header
  height, which is what asks for top-down rows), plus `exclude_from_capture(hwnd)`, the overlay's
  own `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` call.
- A targeted request adds the `focus` module's Z-order walk (`GetTopWindow` then `GW_HWNDNEXT`,
  taking the first window that is visible, not iconic, not DWM-cloaked, not a tool window, not the
  shell window, titled, not this process's, and not excluded from capture; bounds come from
  `DWMWA_EXTENDED_FRAME_BOUNDS`). It is deliberately **not** `GetForegroundWindow`, because the
  overlay is the foreground window whenever a capture runs and hides itself from capture besides.
- **GDI was chosen over DXGI Desktop Duplication and `Windows.Graphics.Capture`** because it needs
  no COM apartment, so it does not deepen the recorded unbalanced-`CoUninitialize` entry; it holds
  no persistent device, so it satisfies the blocking pool's `FnOnce + Send + 'static`; and it has
  the smallest `unsafe` surface. The cost is that it renders hardware-overlay and DRM-protected
  surfaces **black, with no error**.
- **`os_linux`** (`cfg(target_os = "linux")`) has four real backends, `LinuxNotify`,
  `LinuxAudioControl`, `LinuxScreenCapture` and the X11 `LinuxHotkey` (see
  [The Linux backends](#the-linux-backends)), and no stub. The crate is compiled and measured on
  Linux CI. The shell's `BodyService` serves the notification and volume backends with
  `DeniedScreenCapture`, because X11 has no way to keep the overlay out of a picture (ADR-0029
  decision 10 fails closed), and the shell does not register the Linux hotkey yet.
- **`os_macos`** provides `MacosHotkey`, `MacosAudioControl`, `MacosNotify` and
  `MacosScreenCapture`, the same stubs for macOS. It has no `cfg` yet and compiles everywhere.

## Public contract

Each crate exposes one implementor per port, and the app selects the platform's types by
`cfg(target_os)`:

- `Hotkey`: `LinuxHotkey`, `MacosHotkey`, `WindowsHotkey`. `AudioControl`, `Notify` and
  `ScreenCapture` follow the same naming; the Linux `Notify` and `AudioControl` are generic over
  their crate-local ports, `LinuxNotify<DbusNotifications>` and
  `LinuxAudioControl<PactlCommand>` on a real host, and so is `LinuxScreenCapture<X11Root>`.
  `LinuxHotkey` is not generic: it keeps its `KeyGrab` as an `Arc<dyn KeyGrab>`, which its listener
  thread shares, and a real host builds it with `LinuxHotkey::new(X11Keys::new(..))`.
- `AudioControl` (ADR-0023): `get_volume() -> VolumeState` and
  `set_volume(VolumeChange) -> VolumeState`. The value types `VolumeState { level, muted }` and
  `VolumeChange { level, mute }` live in `body_core`, where `VolumeChange::new` clamps a present
  `level` into `[0,1]` (`NaN` to `0.0`) through the pure `clamp_level`, and so does `AudioError`
  (`NoEndpoint` or `Backend`).
- `Notify` (ADR-0025): `show(&Notification) -> Result<bool, NotifyError>`. `Notification` (whose
  constructor applies the inert-text rule), `NotifyError` (`Unavailable` or `Backend`) and the
  `escape_xml` helper a markup renderer calls all live in `body_core`.
- `ScreenCapture` (ADR-0029): `capture(&CaptureRequest) -> Result<CapturedFrame, CaptureError>`,
  which hands back **raw BGRA pixels and no policy at all**. Every size decision (crop, downscale,
  PNG encode, the byte ceiling and its shrink steps) lives in pure `body_core`, because a
  `cfg(windows)` backend does not compile where CI measures coverage and the size guarantee may not
  rest on code CI never measures. That is the `escape_xml` argument again. The one step only a
  backend can perform is resolving the request's `CaptureTarget`, since window positions are known
  only to the OS, and the backend returns that as a rectangle beside the whole frame rather than as
  a crop: widening the **return value** instead of the trait method keeps the port one line and the
  crop arithmetic covered. `DeniedScreenCapture` (in `body_core`, not in a platform crate) is the
  real, covered backend a host wires when capture is switched off, and it returns
  `CaptureError::Disabled` from ordinary code on every platform, so a host with capture off runs a
  tested path rather than an `unimplemented!()` stub.

`AudioControl`, `Notify` and `ScreenCapture` are `Send + Sync`, because the `body_rpc` `BodyService`
server holds all three and lends each to a blocking thread per call, unlike the single-threaded
`Hotkey`. All three stay **synchronous** on purpose: the OS APIs they wrap are synchronous, and an
async signature would present a blocking call as an awaitable one. Moving the call off the async
worker is the server's job (`body_rpc::off_worker`), not the port's.

## `unsafe` in `os_windows`

`os_windows` is the **only** crate that opts out of the workspace `unsafe_code = forbid`, narrowly
authorized by ADR-0023. It uses its own `[lints.rust] unsafe_code = deny` plus a scoped
`#![allow(unsafe_code)]` per module, re-declaring the other workspace lints; every other crate keeps
`forbid`. There are four such modules, each with its own authorization line naming its own decision
record: `audio` (Core Audio, ADR-0023), `notify` (one apartment initialization, ADR-0025), `screen`
(GDI plus the display-affinity call, ADR-0029) and `focus` (the Z-order walk behind a targeted
capture, ADR-0029).

The toast module has the same scoped allow for one line: WinRT projections are safe, but
activating a WinRT factory needs a COM-initialized thread and the `BodyService` server's threads
have none, so it makes the same idempotent `CoInitializeEx` call the audio backend does. Since
2026-07-16 that thread is a **tokio blocking-pool** thread rather than an async worker, which is why
both backends are shaped the way they are: each resolves its own COM interface inside the call and
holds none across calls, so nothing `!Send` is ever moved between threads and a per-call
`CoInitializeEx` is all either needs. Neither balances it with `CoUninitialize`, which is deliberate
and recorded in `docs/refinements/`.

## The Linux backends

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
  No server is `NoDisplay`, a failed layout or read `Backend`, and a window target is refused as
  `Backend` without reading the screen, since no X11 window walk exists yet.
- **`X11Root`** lists the active monitors with RandR 1.5's `GetMonitors`, which reports each
  monitor's primary flag and rectangle in one request; a server without the extension lists none,
  and an X error to the request fails the capture as `Backend`. It then sends one `GetImage`
  (`ZPixmap`, every plane) for the chosen rectangle of the root of one screen of an
  `x11rb::rust_connection::RustConnection` it is given, and reads the bits per pixel, byte order
  and root visual masks from the connection's setup. The crate re-exports `x11rb`, and the host
  opens the display with `x11rb::connect(None)`. When that fails, as on a Wayland session with no
  `DISPLAY`, `X11Root::absent(&error)` makes every read `NoDisplay`. Rootless Xwayland, such as
  WSLg's, answers `GetImage` on its root with `BadMatch`, so the read fails as `Backend` rather
  than returning a partial picture; a Wayland session needs the desktop portal instead.
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
  needs the desktop portal's `GlobalShortcuts`
  ([765](../refinements/tasks/765-a-wayland-hotkey-through-the-globalshortcuts-portal.md)).
- `just os-linux-live` runs the four `#[ignore]`d live tests: a notification shown on the session
  bus, a volume and mute round trip on the default sink that restores what it found, a capture
  of the root window on `DISPLAY` that prints its size and how many pixels are not black, and a
  `ctrl+alt+space` grab that XTEST presses with Num Lock off and on and holds for 1.5 s, each of
  which must run the callback once, and that `ctrl+space` must not run.

## The coverage exemption

`cargo llvm-cov` sets `cfg(coverage)`. Each stub crate opts into the nightly attribute under it,
`#![cfg_attr(coverage, feature(coverage_attribute))]` at the crate root, and marks every unreachable
stub body `#[cfg_attr(coverage, coverage(off))]`. Under a normal `cargo build`, `clippy` or `test`
the `coverage` cfg is unset, so the attributes vanish and the crates compile on stable.
`cfg(coverage)` is declared in the workspace lints (`check-cfg`) so it is not "unexpected". Only
genuinely unreachable code, a stub whose body is `unimplemented!()`, gets the exemption.
`os_windows` is left out of the measurement by being `cfg`'d out on Linux and is validated by host
runs instead; `os_linux`'s real backends are measured in full. Neither silences coverage.

## Invariants

- Thin adapters only: translate `body_core` types to OS calls, with no business logic. The level
  clamp lives in `body_core`, and so do the inert-text rule, the taint attribution and the XML
  escaping. What `os_linux` adds is protocol translation (when to escape, how to parse `pactl`,
  how an X server lays out a pixel), covered by tests over fakes.
- Stubs are `unimplemented!()` with a reason, and `coverage(off)` marks only genuinely unreachable
  code.
- Coverage is measured on **Linux CI**, including every line of `os_linux`. The Windows backends
  are host-validated, which is where the real OS calls in `os_windows` are exercised at all.
- A Linux backend opens no session connection itself: the caller passes the connection, or the
  error of one that did not open, or picks the program, so no measured line depends on a desktop
  session.
- `unsafe` is `forbid` everywhere except `os_windows`, where it is COM only, under `deny` plus a
  scoped `allow` (ADR-0023).

**Dependencies.** `body-core` (the ports). `os_linux` adds `zbus` 5 (MIT, pure Rust, `async-io` and
`blocking-api` features, plus `p2p` for its tests) and `x11rb` 0.13 (MIT or Apache-2.0, pure Rust,
no default features, so no `libxcb`, with `randr`, plus `xtest` for its live test) under a
`cfg(target_os = "linux")` target table; it runs
`pactl` as a program and links no audio or X library. The real `os_windows` adds `global-hotkey`
and the `windows` crate (`0.58`, with Core Audio plus the `UI_Notifications` and `Data_Xml_Dom`
WinRT namespaces), both under `[target.'cfg(windows)'.dependencies]`, so they never build on Linux.
