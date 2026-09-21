# The shell's Windows clippy waits on a resource step

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Trigger:** a release of `tauri-build`, `tauri-winres` or `embed-resource` within the shell's
manifest requirement that lets a build for a target it never links skip the resource step, or the
first `cfg(windows)` failure in the shell that reaches master because the check that would have
caught it does not run at the hook.
**Verified:** 2026-09-17

`check-shell` runs two clippy lines, the host one and
`cargo clippy --locked --target x86_64-pc-windows-msvc --all-targets -- -D warnings`, and CI
schedules both. Neither runs at the pre-commit hook, so a rename or a signature change inside the
shell's six items behind `cfg(windows)` is caught on a runner rather than before the commit. That is
the divergence [ADR-0011](../../adr/ADR-0011-body-v1.md) decision 10 accepted for the host line,
inherited by the Windows one for a narrower reason.

The host line needs the Linux GTK, webkit and dbus dev packages because the shell genuinely depends
on that stack. The Windows line needs none of them: the whole Tauri Windows graph type-checks in
26.1 s with nothing installed but the rust target. It needs exactly one package,
`binutils-mingw-w64-x86-64`, and only because `tauri_build::build()` compiles a VERSIONINFO resource
for every Windows target, through `tauri-winres` and from there `embed-resource`, and hands it to a
compiler that has to exist. No argument to `tauri_build::build()` and no environment variable turns
that step off; the switches `tauri-build` offers (`WindowsAttributes`) choose what goes into the
resource, not whether one is built. A build that never links has no use for the object windres
writes.

If any of the three crates grows a way to skip the resource step, move the Windows clippy out of
`check-shell` into `check-body` beside the `os_windows` clippy, where it belongs on the same
reasoning: a check needing no system library belongs inside the single check. The host line stays
where it is. Do not reach for the other route, a `build.rs` that skips `tauri_build::build()` under
an environment variable the check sets, because the build script is what the real Windows build
depends on and a check that runs a different one proves less than it claims.

## History

- 2026-09-07: opened by the close of [R-595](595-no-gate-compiles-the-tauri-shells-windows-half.md),
  which added the Windows clippy and recorded that its placement outside `just check` rests on the
  resource step alone.
- 2026-09-11: read against the tree and not fired on either part. crates.io reports `tauri-build`
  2.6.3 of 2026-06-30 and `embed-resource` 3.0.11 of 2026-07-02 as the newest stable releases, which
  are the versions `body/app/src-tauri/Cargo.lock` fixes, and no commit has touched
  `body/app/src-tauri/` since 2026-09-07. The mechanism is as written: `check-shell` runs both lines
  with `RC_x86_64_pc_windows_msvc` defaulted to the mingw windres, the `check` recipe does not name
  it and the hook runs `just check`, the shell has six `#[cfg(windows)]` items, four in
  `body_server.rs` and two in `hotkey.rs`, `build.rs` is the one call to `tauri_build::build()`, and
  `ci.yml` installs `binutils-mingw-w64-x86-64` beside the five Linux roots. Where this overlaps the
  entry about the shell job never having run: the line CI schedules here has run on a runner as many
  times as the host line, which is never, so its runner half is unproven on the same terms. The 26.1
  s type-check was not run again, since the windres is not installed here.
- 2026-09-17: not fired on either part, with two corrections. The resource step has a third crate in
  it: `tauri-build` calls `tauri-winres` 0.3.6, which is what depends on `embed-resource` in
  `body/app/src-tauri/Cargo.lock`, so the trigger and the closing sentence now name all three. And
  crates.io dates `tauri-build` 2.6.3 to 2026-06-17, not 2026-06-30. The newest stable releases are
  still the fixed 2.6.3, 0.3.6 of 2026-04-27 and 3.0.11. A pre-release, `tauri-build` 3.0.0-alpha.0,
  appeared on 2026-09-13; the shell's manifest asks for `"2"`, so it cannot be selected, and its
  source was read anyway: `src/lib.rs` still builds a `WindowsResource` and calls `compile()` for
  any target triple containing `windows` (lines 751 to 824), with no switch around it. One commit
  has touched `body/app/src-tauri/` since 2026-09-07, a one-line default in a doc comment in
  `brain.rs`. The six items, the one `build.rs:2` call and `check-shell` (`justfile:265`) are
  unchanged.
