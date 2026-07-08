# body/crates/os_* (per-platform OS backends)

**Purpose.** The adapter side of the body's OS-capability seam (ADR-0011): each crate
implements the `body_core::os` port traits for one platform. This is the first `cfg`-gated
OS backend and the home of the **stub coverage escape-hatch policy** the ROADMAP marks
"gate proven" at Slice 8. The ports and all pure logic live in `body_core`
(`docs/modules/body-core.md`); these crates only translate to OS calls.

- **`os_windows`** (`os_windows`, `cfg(windows)`) is the real backend. *`WindowsHotkey`
  landed in Slice 8 increment 3;* wraps the `global-hotkey` crate to keep
  `unsafe_code = forbid`. *Slice 9 added `WindowsAudioControl`* over Core Audio
  (`IMMDeviceEnumerator` → `IAudioEndpointVolume`). Real OS calls → a thin adapter,
  **host/integration-validated, never in CI** (AGENTS.md gate 3): the coverage gate runs
  on Linux, where this crate compiles to nothing. The audio backend needs `unsafe` (COM),
  narrowly authorized by ADR-0023: `os_windows` is the **only** crate that opts out of the
  workspace `unsafe_code = forbid`, using its own `[lints.rust] unsafe_code = deny` plus a
  scoped `#![allow(unsafe_code)]` in the audio module (re-declaring the other workspace
  lints); every other crate keeps `forbid`.
- **`os_linux`** (`os_linux`) provides `LinuxHotkey` and `LinuxAudioControl`, `unimplemented!()`
  stubs (Windows-first). Compiled and measured on Linux CI, so each stub method is
  `#[cfg_attr(coverage, coverage(off))]` with a reason. That is the escape hatch in action.
- **`os_macos`** (`os_macos`) provides `MacosHotkey` and `MacosAudioControl`, the same stubs for
  macOS.

**Public contract.** Each crate exposes one `Hotkey` implementor (`LinuxHotkey`,
`MacosHotkey`, and `WindowsHotkey` from increment 3) and, from Slice 9, one `AudioControl`
implementor (`Linux`/`Macos`/`WindowsAudioControl`); the app selects the platform's types by
`cfg(target_os)`. `AudioControl: Send + Sync` (the `body_rpc` tonic `BodyService` server
holds it), unlike the single-threaded `Hotkey`. The ports and pure values live in `body_core`
(`docs/modules/body-core.md`): `AudioControl` (`get_volume() -> VolumeState`,
`set_volume(VolumeChange) -> VolumeState`), the value types `VolumeState { level, muted }`
and `VolumeChange { level, mute }` (`VolumeChange::new` clamps a present `level` to `[0,1]`,
`NaN → 0.0`, via the pure `clamp_level`, which is gated core logic), and `AudioError`
(`NoEndpoint`/`Backend`). Screen/input backends join these crates in Slice 10.

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
  `clamp_level` clamp lives in `body_core`, not here).
- Stubs `unimplemented!()` with a reason; `coverage(off)` only on genuinely unreachable code.
- The coverage gate is a **Linux-CI** gate; Windows/macOS backends are host-validated.
- `unsafe` is `forbid` everywhere except `os_windows` (COM only, `deny` + scoped `allow`,
  ADR-0023).

**Dependencies.** `body-core` (the ports). The real `os_windows` adds `global-hotkey` and, in
Slice 9's `windows` crate (`0.58`, Core Audio), both under
`[target.'cfg(windows)'.dependencies]`, so they never build on Linux.
