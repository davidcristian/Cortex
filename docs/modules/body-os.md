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
- **`os_linux`** (`cfg(target_os = "linux")`) has nine real backends, `LinuxNotify`,
  `LinuxAudioControl`, the X11 `LinuxScreenCapture`, the portal's `LinuxPortalCapture` and
  `LinuxWindowCapture`, the X11
  `LinuxHotkey`, `LinuxKdeHotkey`, the portal's `LinuxPortalHotkey` and the X11
  `LinuxClipboardPicture` (see
  [body-os-linux.md](body-os-linux.md) and [body-os-linux-capture.md](body-os-linux-capture.md)),
  and no stub. The shell's `BodyService`
  serves the notification and volume backends, and `LinuxScreenCapture<X11Root>` only when
  `CORTEX_HOST_CAPTURE=1`, `WAYLAND_DISPLAY` is unset or empty and the X display opens; with the
  switch and `WAYLAND_DISPLAY` set it serves `LinuxPortalCapture` inside `HiddenOverlayCapture`,
  behind a `TargetRouter` that sends a focus request to `LinuxWindowCapture` when the `ScreenCast`
  portal offers a window source, else `DeniedScreenCapture`. The shell registers the hotkey through `X11Keys`, or on a Wayland
  session on a thread of its own through `LinuxKdeHotkey` where `kglobalaccel` runs, else
  `LinuxPortalHotkey`
  ([overlay runbook](../runbooks/body-overlay.md)). The shell's `clipboard_picture` command opens
  the X display on each paste and reads through `LinuxClipboardPicture<X11Selection>`; the other
  platforms answer with `body_core::NoClipboardPicture`.
- **`os_macos`** provides `MacosHotkey`, `MacosAudioControl`, `MacosNotify`,
  `MacosScreenCapture` and `MacosClipboardPicture`, the same stubs for macOS. It has no `cfg` yet and compiles everywhere.

## Public contract

Each crate exposes one implementor per port, and the app selects the platform's types by
`cfg(target_os)`:

- `Hotkey`: `LinuxHotkey`, `MacosHotkey`, `WindowsHotkey`. `AudioControl`, `Notify` and
  `ScreenCapture` follow the same naming; the Linux `Notify` and `AudioControl` are generic over
  their crate-local ports, `LinuxNotify<DbusNotifications>` and
  `LinuxAudioControl<PactlCommand>` on a real host, and so are `LinuxScreenCapture<X11Root>` and
  `LinuxPortalCapture<DbusPortal>`.
  `LinuxHotkey` is not generic: it keeps its `KeyGrab` as an `Arc<dyn KeyGrab>`, which its listener
  thread shares, and a real host builds it with `LinuxHotkey::new(X11Keys::new(..))`.
  `LinuxPortalHotkey` keeps its `ShortcutsPortal` the same way, built over `DbusShortcuts`, and
  `LinuxKdeHotkey` its `GlobalAccel`, built over `DbusGlobalAccel`.
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
  rest on code CI never measures. The one step only a backend can perform is resolving the request's
  `CaptureTarget`, since window positions are known only to the OS, and the backend returns that as
  a rectangle beside the whole frame rather than as a crop: widening the **return value** instead of
  the trait method keeps the port one line and the crop arithmetic covered. `DeniedScreenCapture`
  (in `body_core`, not in a platform crate) is the real, covered backend a host wires when capture
  is switched off, and it returns `CaptureError::Disabled` from ordinary code on every platform, so
  a host with capture off runs a tested path rather than an `unimplemented!()` stub.

`AudioControl`, `Notify` and `ScreenCapture` are `Send + Sync`, because the `body_rpc` `BodyService`
server holds all three and lends each to a blocking thread per call, unlike the single-threaded
`Hotkey`. All three stay **synchronous** on purpose: the OS APIs they wrap are synchronous, and an
async signature would present a blocking call as an awaitable one. Moving the call off the async
worker is the server's job (`body_rpc::off_worker`), not the port's.

## `unsafe` in `os_windows`

`os_windows` is the **only** crate that opts out of the workspace `unsafe_code = forbid`, narrowly
authorized by ADR-0023. It uses its own `[lints.rust] unsafe_code = deny` plus a scoped
`#![allow(unsafe_code)]` per module, re-declaring the other workspace lints; every other crate keeps
`forbid`. There are four such modules, each allow's comment naming the API that needs it and each
resting on its own decision record: `audio` (Core Audio, ADR-0023), `notify` (one apartment
initialization, ADR-0025), `screen` (GDI plus the display-affinity call, ADR-0029) and `focus` (the
Z-order walk behind a targeted capture, ADR-0029).

The toast module has the same scoped allow for one line: WinRT projections are safe, but activating
a WinRT factory needs a COM-initialized thread and the `BodyService` server's threads have none, so
it makes the same idempotent `CoInitializeEx` call the audio backend does. That thread is a **tokio
blocking-pool** thread rather than an async worker, so each backend resolves its own COM interface
inside the call and holds none across calls: nothing `!Send` moves between threads, and a per-call
`CoInitializeEx` is all either needs. Neither balances it with `CoUninitialize`, which is deliberate
and recorded in `docs/refinements/`.

## The coverage exemption

`cargo llvm-cov` sets `cfg(coverage)`. Each stub crate opts into the nightly attribute under it,
`#![cfg_attr(coverage, feature(coverage_attribute))]` at the crate root, and marks every unreachable
stub body `#[cfg_attr(coverage, coverage(off))]`. Under a normal `cargo build`, `clippy` or `test`
the `coverage` cfg is unset, so the attributes vanish and the crates compile on stable.
`cfg(coverage)` is declared in the workspace lints (`check-cfg`) so it is not "unexpected". Only
genuinely unreachable code, a stub whose body is `unimplemented!()`, gets the exemption.

## Invariants

- Thin adapters only: translate `body_core` types to OS calls, with no business logic. The level
  clamp lives in `body_core`, and so do the inert-text rule, the taint attribution and the XML
  escaping. What `os_linux` adds is protocol translation (when to escape, how to parse `pactl`,
  how an X server lays out a pixel), covered by tests over fakes.
- Each Linux backend runs its port's shared list ([body-contract.md](body-contract.md)), so it and
  its fake are held to one description: `LinuxAudioControl` over a stand-in sound server
  (`tests/audio_contract.rs`), `LinuxNotify` over `FakeBus` (`tests/notify.rs`),
  `LinuxScreenCapture` over `FakeRoot` (`tests/screen.rs`) and `LinuxHotkey` over `FakeKeys`
  (`tests/hotkey.rs`). `LinuxPortalCapture` does not, because the list's focus checks need a window
  and a portal picture names none; its own tests are `tests/portal.rs` and `tests/portal_dbus.rs`.
- Stubs are `unimplemented!()` with a reason, and only they are marked `coverage(off)`.
- Coverage is measured on **Linux CI**, including every line of `os_linux`. The Windows backends
  are host-validated, which is where the real OS calls in `os_windows` are exercised at all.
- A Linux backend opens no session connection itself: the caller passes the connection, or the
  error of one that did not open, or picks the program, so no measured line depends on a desktop
  session.
- `unsafe` is `forbid` everywhere except `os_windows`, where it is COM only, under `deny` plus a
  scoped `allow` (ADR-0023).

**Dependencies.** `body-core` (the ports). `os_linux` adds `zbus` 5 (MIT, pure Rust, `async-io` and
`blocking-api` features, plus `p2p` and `bus-impl` for its tests), `png` 0.18 (MIT or
Apache-2.0, the version `body-core` encodes with) and `x11rb` 0.13 (MIT or Apache-2.0, pure Rust,
no default features, so no `libxcb`, with `randr`, plus `xtest` for its live test) under a
`cfg(target_os = "linux")` target table, and `body-contract` for its tests; it runs
`pactl` as a program and links no audio or X library. The real `os_windows` adds `global-hotkey`
and the `windows` crate (`0.61`, with Core Audio plus the `UI_Notifications` and `Data_Xml_Dom`
WinRT namespaces), both under `[target.'cfg(windows)'.dependencies]`, so they never build on Linux.
