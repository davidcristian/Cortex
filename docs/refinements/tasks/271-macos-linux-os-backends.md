# macOS and Linux OS backends

**Status:** open, optional feature
**Area:** cross-cutting
**Origin:** none, this area is the old catch-all list and has no single origin decision record
**Verified:** 2026-09-13

Real macOS and Linux backends behind the existing OS traits. Today both crates satisfy `Hotkey`,
`AudioControl`, `Notify` and `ScreenCapture` with `unimplemented!()`.

The Linux half costs more than one line suggests, because of a coverage problem no document
records. `os_windows` is excluded from the Linux coverage run by construction, being
`#[cfg(windows)]` with even its dependencies declared under
`[target.'cfg(windows)'.dependencies]`, while `body/crates/os_linux/src/lib.rs` and
`body/crates/os_macos/src/lib.rs` are plain workspace members with a bare `[dependencies]`, whose
stubs sit under `#[cfg_attr(coverage, coverage(off))]` with an inline reason. Since the coverage
run passes `--workspace`, a real Linux backend would compile in CI and be measured, putting live
X11 or Wayland calls inside the 100% line and branch requirement, which is exactly where AGENTS.md
does not put real OS calls: those belong in thin adapters under `integration` marking, run on the
host. Both halves of that collision are written down separately, in
[body-os.md](../../modules/body-os.md), which records `os_linux` as compiled and measured on Linux
CI, and in the crate's own header, which records that real backends are host-validated and never in
CI. Whoever picks this up needs the integration-marking answer before writing a line of X11. The
macOS half does not have the problem, because a real macOS backend could not compile on Linux at
all and would have to take `os_windows`'s `cfg` attribute, which also means
[ADR-0011](../../adr/ADR-0011-body-v1.md) decision 3 describes `os_macos` as `cfg(macos)` where the
crate has no such attribute.

This stays a refinement rather than moving to [docs/host/](../../host/index.md), which holds work
needing a Win32 desktop session or a 24 GB GPU: a Linux or macOS backend needs neither.

## History

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section as one clause of the
  "Later, unordered" list.
- 2026-08-09: A costing pass found the coverage problem above, which is the reason the entry reads
  cheaper than it is, and wrote it down rather than changing the entry.
- 2026-09-13: Checked again and every substantive claim holds, while four cited pointers had moved.
  `os_linux` and `os_macos` are 70 lines each rather than 71, the coverage run is at
  `justfile:233` rather than 95 and still passes `--workspace`, the two halves of the collision are
  at [body-os.md](../../modules/body-os.md) line 51 rather than 42 and at the crate header lines 7
  to 8 rather than 7 to 9, and the origin decision still describes `os_macos` as `cfg(macos)`.
