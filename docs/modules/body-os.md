# body/crates/os_* (per-platform OS backends)

**Purpose.** The adapter side of the body's OS-capability seam (ADR-0011): each crate
implements the `body_core::os` port traits for one platform. This is the first `cfg`-gated
OS backend and the home of the **stub coverage escape-hatch policy** the ROADMAP marks
"gate proven" at Slice 8. The ports and all pure logic live in `body_core`
(`docs/modules/body-core.md`); these crates only translate to OS calls.

- **`os_windows`** (`os_windows`, `cfg(windows)`) is the real backend. *`WindowsHotkey`
  landed in Slice 8 increment 3;* wraps the `global-hotkey` crate to keep
  `unsafe_code = forbid`. *Slice 9 added `WindowsAudioControl`* over Core Audio
  (`IMMDeviceEnumerator` → `IAudioEndpointVolume`). *Slice 9.5 added `WindowsNotify`*, a
  WinRT toast (`ToastNotificationManager` → `ToastNotifier`, rendering the `ToastGeneric`
  template). Real OS calls → a thin adapter,
  **host/integration-validated, never in CI** (AGENTS.md gate 3): the coverage gate runs
  on Linux, where this crate compiles to nothing. The audio backend needs `unsafe` (COM),
  narrowly authorized by ADR-0023: `os_windows` is the **only** crate that opts out of the
  workspace `unsafe_code = forbid`, using its own `[lints.rust] unsafe_code = deny` plus a
  scoped `#![allow(unsafe_code)]` in the audio module (re-declaring the other workspace
  lints); every other crate keeps `forbid`. The toast module carries the same scoped allow for
  one line: WinRT projections are safe, but activating a WinRT factory needs a
  COM-initialized thread and the `BodyService` server's threads have none, so
  it makes the same idempotent `CoInitializeEx` call the audio backend does.
  Since 2026-07-16 that thread is a **tokio blocking-pool** thread rather than an async
  worker (`body_rpc::off_worker`), which is what makes both backends' shape load-bearing:
  each resolves its own COM interface inside the call and holds none across calls, so nothing
  `!Send` is ever moved between threads and a per-call `CoInitializeEx` is all either needs.
  Neither balances it with `CoUninitialize`, which is deliberate and recorded
  (`docs/refinements/body-gateway.md`).
- **`os_linux`** (`os_linux`) provides `LinuxHotkey`, `LinuxAudioControl`, `LinuxNotify`, and
  `LinuxScreenCapture`,
  `unimplemented!()` stubs (Windows-first). Compiled and measured on Linux CI, so each stub method is
  `#[cfg_attr(coverage, coverage(off))]` with a reason. That is the escape hatch in action.
- **`os_macos`** (`os_macos`) provides `MacosHotkey`, `MacosAudioControl`, `MacosNotify`, and
  `MacosScreenCapture`, the same stubs for macOS.

**Public contract.** Each crate exposes one `Hotkey` implementor (`LinuxHotkey`,
`MacosHotkey`, and `WindowsHotkey` from increment 3), from Slice 9 one `AudioControl`
implementor (`Linux`/`Macos`/`WindowsAudioControl`), and from Slice 9.5 one `Notify`
implementor (`Linux`/`Macos`/`WindowsNotify`); the app selects the platform's types by
`cfg(target_os)`. `AudioControl` and `Notify` are `Send + Sync` (the `body_rpc` tonic
`BodyService` server holds both, and lends each to a blocking thread per call), unlike the
single-threaded `Hotkey`. Both ports stay **synchronous** on purpose: the OS they wrap is,
and an async signature would only wrap a blocking call in a lie. Getting it off the async
worker is the server's job, not the port's. The ports and pure
values live in `body_core`
(`docs/modules/body-core.md`): `AudioControl` (`get_volume() -> VolumeState`,
`set_volume(VolumeChange) -> VolumeState`), the value types `VolumeState { level, muted }`
and `VolumeChange { level, mute }` (`VolumeChange::new` clamps a present `level` to `[0,1]`,
`NaN → 0.0`, via the pure `clamp_level`, which is gated core logic), and `AudioError`
(`NoEndpoint`/`Backend`); `Notify` (`show(&Notification) -> Result<bool, NotifyError>`) with
`Notification` (whose constructor applies the inert-text rule), `NotifyError`
(`Unavailable`/`Backend`), and the `escape_xml` helper a markup renderer calls.
`WindowsNotify::new(app_id)` takes the `AppUserModelID` the toast is attributed to, which an
unpackaged app must own a Start Menu shortcut for (`CORTEX_TOAST_APP_ID` at the shell;
`docs/runbooks/scheduling.md`).

Slice 10 adds a third port, `ScreenCapture` (ADR-0029), also `Send + Sync` and also
synchronous. Its shape is deliberately unlike the other two: `capture(&CaptureRequest) ->
Result<RawFrame, CaptureError>` hands back **raw BGRA pixels and no policy at all**. Every
size decision (downscale, PNG encode, the byte ceiling and its shrink ladder) lives in pure
`body_core`, because a `cfg(windows)` backend is invisible to the coverage gate and the seam's
size guarantee may not rest on code CI never measures. That is the `escape_xml` argument
verbatim. `CaptureError` is `NoDisplay`/`Disabled`/`Backend`/`TooLarge`, and
`DeniedScreenCapture` (in `body_core`, not in a platform crate) is the real, gated backend a
host wires when capture is switched off: refusing is a capability, not a missing platform.
Input backends join later.

**The escape hatch (how the 100% gate stays honest).** `cargo llvm-cov` sets `cfg(coverage)`;
each stub crate opts into the nightly attribute under it,
`#![cfg_attr(coverage, feature(coverage_attribute))]` at the crate root. Each stub also marks every
unreachable stub body `#[cfg_attr(coverage, coverage(off))]`. Under a normal `cargo build`/
`clippy`/`test` the `coverage` cfg is unset, so the attributes vanish and the crates compile
on stable. `cfg(coverage)` is declared in the workspace lints (`check-cfg`) so it is not
"unexpected". Only genuinely unreachable code (a stub whose body is `unimplemented!()`) gets
the hatch. Real backends are excluded from the gate by being `cfg`'d out on Linux and
validated by host/integration runs instead, never by silencing coverage.

**Invariants.**
- Thin adapters only: translate `body_core` types to OS calls, no business logic (the
  `clamp_level` clamp lives in `body_core`, and so do the toast's inert-text rule, its taint
  attribution, and its XML escaping, none of which this crate decides).
- Stubs `unimplemented!()` with a reason; `coverage(off)` only on genuinely unreachable code.
- The coverage gate is a **Linux-CI** gate; Windows/macOS backends are host-validated.
- `unsafe` is `forbid` everywhere except `os_windows` (COM only, `deny` + scoped `allow`,
  ADR-0023).

**Dependencies.** `body-core` (the ports). The real `os_windows` adds `global-hotkey` and the
`windows` crate (`0.58`; Core Audio from Slice 9, plus the `UI_Notifications` / `Data_Xml_Dom`
WinRT namespaces from Slice 9.5), both under
`[target.'cfg(windows)'.dependencies]`, so they never build on Linux.
