# Linux and macOS `ScreenCapture` backends

**Status:** open, feature breadth
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Both crates carry `unimplemented!()` stubs that
satisfy the trait, like every other OS port.

## Trail

- 2026-07-18: recorded in this area when the vision slice landed.
- 2026-07-19: the index grouped it with the `Windows.Graphics.Capture` backend and called it the
  same ask as the macOS/Linux OS backends line above it.
- 2026-08-09: a costing pass against the tree found a coverage trap no doc records, and it is the
  reason the entry reads cheaper than it is. `os_windows` escapes the Linux coverage run by
  construction, the crate being `#[cfg(windows)]` with even its dependencies declared under
  `[target.'cfg(windows)'.dependencies]`, so on Linux it builds to nothing. The two stub crates are
  not gated that way: `body/crates/os_linux/src/lib.rs` and `body/crates/os_macos/src/lib.rs` are 71
  lines each, plain workspace members (`body/Cargo.toml:2`) with a bare `[dependencies]`, each
  satisfying `Hotkey`, `AudioControl`, `Notify` and `ScreenCapture` with `unimplemented!()` under
  `#[cfg_attr(coverage, coverage(off))]` with an inline reason. Since the gate runs `cargo llvm-cov
  --workspace` (`justfile:95`), a real Linux backend would compile in CI and be measured, putting
  live X11 or Wayland calls inside the 100 percent line and branch gate, which is precisely where
  AGENTS.md does not put real OS calls. Both halves of that collision are already written down and
  never joined, at [body-os.md](../../modules/body-os.md) line 42 and the crate's own header at lines 7
  to 9, so whoever picks this up needs the integration-marking answer before writing a line of X11.
  The macOS half does not have the problem, because a real macOS backend could not compile on Linux
  at all and would have to gain `os_windows`'s `cfg` gate, which also means ADR-0011's decision 3
  describes a gate `os_macos` does not currently carry.
- 2026-08-09: the same pass re-read the entry and left it parked exactly as written, nothing about
  it changed. The capture stubs are the `unimplemented!()` pair at line 64 of each crate's `lib.rs`,
  so the Linux side inherits the coverage question above while the `Windows.Graphics.Capture`
  argument beside it is untouched. What the pass changed is what the next reader should expect to
  pay rather than anything the entry says.
