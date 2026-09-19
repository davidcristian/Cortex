# Linux and macOS `ScreenCapture` backends

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-13

Both crates have `unimplemented!()` stubs that satisfy the trait, like every other OS port.

The Linux half costs more than that suggests, because of a coverage problem no document records.
`os_windows` is excluded from the Linux coverage run by construction: the crate is
`#[cfg(windows)]`, with even its dependencies declared under `[target.'cfg(windows)'.dependencies]`,
so on Linux it builds to nothing. The two stub crates are not written that way.
`body/crates/os_linux/src/lib.rs` and `body/crates/os_macos/src/lib.rs` are plain workspace members
with a bare `[dependencies]`, each satisfying `Hotkey`, `AudioControl`, `Notify` and
`ScreenCapture` with `unimplemented!()` under `#[cfg_attr(coverage, coverage(off))]` and an inline
reason. Since the check runs `cargo llvm-cov --workspace`, a real Linux backend would compile in CI
and be measured, putting live X11 or Wayland calls inside the 100% line and branch requirement,
which is exactly where AGENTS.md does not put real OS calls. Both halves of that collision are
written down separately and never joined, in [body-os.md](../../modules/body-os.md) and the crate's
own header, so whoever picks this up needs the integration-marking answer before writing a line of
X11. The macOS half does not have the problem, because a real macOS backend could not compile on
Linux at all and would have to take `os_windows`'s `cfg` attribute, which also means ADR-0011's
decision 3 describes an attribute `os_macos` does not have.

## History

- 2026-07-18: Recorded when the vision slice was finished.
- 2026-07-19: Grouped with the `Windows.Graphics.Capture` backend, as the same request as the macOS
  and Linux OS backends entry.
- 2026-08-09: A costing pass found the coverage problem above, which is why the entry reads cheaper
  than it is, and left the entry itself as written.
- 2026-09-13: Checked again. Every essential claim holds and three citations have moved. Both stub
  crates are 70 lines rather than 71, each capture stub is the `fn capture` at line 65, and the
  coverage half of the collision is now in [body-os.md](../../modules/body-os.md)'s escape-hatch
  section rather than at line 42. Neither stub crate has a `cfg(target_os)` attribute, in its
  source or its manifest, so both still compile and are measured on Linux while `os_windows` still
  builds to nothing there.
