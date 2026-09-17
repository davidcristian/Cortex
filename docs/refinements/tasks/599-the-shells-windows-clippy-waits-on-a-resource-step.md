# The shell's Windows clippy waits on a resource step

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Trigger:** a release of `tauri-build`, `tauri-winres` or `embed-resource` within the shell's
manifest requirement that lets a build for a target it never links skip the resource step, or the
first `cfg(windows)` red in the shell that reaches master because the check that would have caught
it does not run at the hook.
**Verified:** 2026-09-17

Opened 2026-09-07 by the close of
[R-595](595-no-gate-compiles-the-tauri-shells-windows-half.md), which put the shell's
`#[cfg(windows)]` items under a compiler for the first time and had to put that compiler outside
`just check` to do it.

**What the gap is.** `check-shell` now runs two clippy lines, the host one and
`cargo clippy --locked --target x86_64-pc-windows-msvc --all-targets -- -D warnings`, and CI
schedules both. Neither runs at the pre-commit hook, so a rename or a signature change inside the
shell's six Windows-gated items is caught on a runner rather than before the commit. That is the
divergence [ADR-0011](../../adr/ADR-0011-body-v1.md)'s 2026-08-17 addendum accepted for the host
line, inherited by the Windows one for a narrower reason than the one that justified it.

**Why the reason is narrower.** The host line needs the Linux GTK/webkit/dbus dev packages because
the shell genuinely depends on that stack. The Windows line needs none of them: the whole Tauri
Windows graph type-checks in 26.1 s with nothing installed but the rust target. It needs exactly
one package, `binutils-mingw-w64-x86-64`, and only because `tauri_build::build()` compiles a
VERSIONINFO resource for every Windows target, through `tauri-winres` and from there
`embed-resource`, and hands it to a compiler that has to exist. No
argument to `tauri_build::build()` and no environment variable turns that step off; the switches
`tauri-build` offers (`WindowsAttributes`) choose what goes into the resource, not whether one is
built. A build never linked has no use for the object windres writes, so the step is pure cost for
this check.

**What would close it.** If any of the three crates grows a way to skip the resource step, move the Windows
clippy out of `check-shell` into `check-body` beside the `os_windows` windows-target clippy, where
it belongs on the same reasoning: a check needing no system library belongs inside the single gate.
The host line stays where it is. Do not reach for the other route, a `build.rs` that skips
`tauri_build::build()` under an environment variable the check sets, because the build script is
what the real Windows build depends on and a check that runs a different one proves less than it
claims.

## Trail

- 2026-09-07: opened by the close of
  [R-595](595-no-gate-compiles-the-tauri-shells-windows-half.md), which landed the Windows clippy
  and recorded that its placement outside `just check` rests on the resource step alone.
- 2026-09-11: read against the tree and not fired on either arm. crates.io reports `tauri-build`
  2.6.3 of 2026-06-30 and `embed-resource` 3.0.11 of 2026-07-02 as the newest stable releases,
  which are the versions `body/app/src-tauri/Cargo.lock` pins, so no release has arrived since
  this was opened; and no commit has touched `body/app/src-tauri/` since 2026-09-07, so no
  Windows red has reached master. The mechanism is as written: `check-shell` runs the host line
  and the `x86_64-pc-windows-msvc` line with `RC_x86_64_pc_windows_msvc` defaulted to the mingw
  windres, the `check` recipe does not name it and the hook runs `just check`, the shell carries
  six `#[cfg(windows)]` items, four in `body_server.rs` and two in `hotkey.rs`, `build.rs` is
  the one call to `tauri_build::build()`, and `ci.yml` installs `binutils-mingw-w64-x86-64`
  beside the five Linux roots. Where this overlaps the entry about the shell job never having
  run: the line CI schedules here has run on a runner as many times as the host line, which is
  never, so its runner half, the package, the windres path and the target install, is unproven
  on the same terms and closes on that entry's trigger. The 26.1 s type-check was not re-run;
  the windres is not installed here.
- 2026-09-17: not fired on either arm, with two corrections. The resource step has a third crate
  in it: `tauri-build` calls `tauri-winres` 0.3.6, which is the one that depends on
  `embed-resource` in `body/app/src-tauri/Cargo.lock`, so the trigger and the closing sentence now
  name all three. And crates.io dates `tauri-build` 2.6.3 to 2026-06-17, not 2026-06-30. The newest
  stable releases are still the pinned 2.6.3, 0.3.6 of 2026-04-27 and 3.0.11. A pre-release,
  `tauri-build` 3.0.0-alpha.0, appeared on 2026-09-13; the shell's manifest asks for `"2"`, so it
  cannot be selected, and its source was read anyway: `src/lib.rs` still builds a
  `WindowsResource` and calls `compile()` for any target triple containing `windows` (lines 751 to
  824), with no switch around it. One commit has touched `body/app/src-tauri/` since 2026-09-07, a
  one-line default in a doc comment in `seam.rs`, which cannot turn a `cfg(windows)` item red. The
  six items are still four in `body_server.rs` and two in `hotkey.rs`, `build.rs:2` is still the
  one call, and `check-shell` (`justfile:265`) still defaults `RC_x86_64_pc_windows_msvc` to the
  mingw windres. The runner half is still unrun, now read against the remote on the shell job's
  entry.
