# macOS and Linux OS backends

**Status:** open, feature breadth
**Area:** cross-cutting
**Origin:** none, this area is the old catch-all list and has no single origin decision record

macOS/Linux OS backends.

That fragment was recorded inside the area's one grouped entry, "Cross-cutting (originally 'Later,
unordered')", which lists it beside pointer-input injection, richer memory policies and more
subagent roles and never gave it a bullet of its own.

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section as one clause of the
  "Later, unordered" list, and carried in the index's feature-breadth bucket as "macOS/Linux OS
  backends behind the existing traits".
- 2026-08-09: A costing pass over that bucket read the entry against the tree and found a coverage
  trap no doc records, which is the reason it reads cheaper than it is: `os_windows` escapes the
  Linux coverage run by construction, being `#[cfg(windows)]` with even its dependencies declared
  under `[target.'cfg(windows)'.dependencies]`, while `body/crates/os_linux/src/lib.rs` and
  `body/crates/os_macos/src/lib.rs` are plain workspace members of 71 lines each with a bare
  `[dependencies]` (`body/Cargo.toml:2`) that satisfy `Hotkey`, `AudioControl`, `Notify` and
  `ScreenCapture` with `unimplemented!()` under `#[cfg_attr(coverage, coverage(off))]` with an
  inline reason, so a real Linux backend would compile in CI and be measured by
  `cargo llvm-cov --workspace` (`justfile:95`), putting live X11 or Wayland calls inside the 100
  percent line and branch gate, which is precisely where AGENTS.md does not put real OS calls: those
  belong in thin adapters under `integration` marking, run on the host and excluded from the gate.
  Both halves of that collision were already written down and never joined, at
  [body-os.md](../../modules/body-os.md) line 42, which records `os_linux` as compiled and measured
  on Linux CI, and at the crate's own header lines 7 to 9, which records that real backends are
  host-validated and never in CI, so whoever picks this up needs the integration-marking answer
  before writing a line of X11. The macOS half does not have the problem, because a real macOS
  backend could not compile on Linux at all and would have to gain `os_windows`'s `cfg` gate, which
  also means ADR-0011's decision 3 describes `os_macos` as `cfg(macos)` and compiling to nothing on
  Linux where the crate carries no such gate today and is spared only by the per-method escape
  hatch. Nothing opened and nothing closed in that pass, and the index recorded this trap as the
  finding of the pass itself, writing it there rather than into this entry, so what the pass
  changed is what the next reader should expect to pay.
