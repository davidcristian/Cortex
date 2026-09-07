# The shell's Windows clippy waits on a resource step

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Trigger:** a `tauri-build` or `embed-resource` release that lets a build for a target it never
links skip the resource step, or the first `cfg(windows)` red in the shell that reaches master
because the check that would have caught it does not run at the hook.

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
VERSIONINFO resource for every Windows target and hands it to a compiler that has to exist. No
argument to `tauri_build::build()` and no environment variable turns that step off; the switches
`tauri-build` offers (`WindowsAttributes`) choose what goes into the resource, not whether one is
built. A build never linked has no use for the object windres writes, so the step is pure cost for
this check.

**What would close it.** If either crate grows a way to skip the resource step, move the Windows
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
