# No check compiles the Tauri shell's Windows half

**Status:** done 2026-09-07
**Area:** repo-checks
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

`just check-shell` and the CI `shell` job both ran `cargo clippy --locked --all-targets` in
`body/app/src-tauri` for the host triple, which is Linux in both places. Two files there have six
`#[cfg(windows)]` items, about a hundred lines: `body_server.rs` declares `DEFAULT_BODY_PORT` and
`DEFAULT_TOAST_APP_ID` and defines the real `start` and `exclude_overlay`, and `hotkey.rs` defines
the real `register` and `configured_chord`. The compiler leaves every one of them out. `check-body`
fmt-checks the shell and rustfmt follows the module tree without evaluating `cfg`, so those lines
are formatted and never type-checked. The neighbouring crate does not have this hole: `check-body`
runs `cargo clippy --target x86_64-pc-windows-msvc -p os-windows`
([ADR-0011](../../adr/ADR-0011-body-v1.md) decision 9).

So a rename, a signature change or a type error inside those items is found on a Windows box or not
at all. `DEFAULT_BODY_PORT` is the worked example: `scripts/crosscheck.py` reads it as text on every
`just check` and compares 23 far sides with it, and no compiler had ever seen the item.

Measured 2026-09-07:
`cargo clippy --locked --target x86_64-pc-windows-msvc --all-targets -- -D warnings` in
`body/app/src-tauri` type-checks the whole Tauri Windows graph and then fails in `cortex-body`'s own
build script, where `tauri-winres` panics with
`called Result::unwrap() on an Err value: NotAttempted("llvm-rc")`, a resource compiler this host
does not have. What the reading did not need is the interesting half: no GTK, no webkit, no dbus and
no pkg-config shim, because the Linux desktop stack is not in the Windows dependency graph.

## History

- 2026-09-07: opened by the close of
  [R-593](593-the-bodys-bind-port-can-be-declared-now-the-shell-compiles.md), which found that the
  reason that entry gave for being unblocked does not hold for a `cfg(windows)` constant under a
  Linux clippy.
- 2026-09-07: done as a second line inside `check-shell`,
  `cargo clippy --locked --target x86_64-pc-windows-msvc --all-targets -- -D warnings` in
  `body/app/src-tauri`, with the CI `shell` job installing the target and one more package on the
  apt line it already runs. Everything measured above was confirmed: six `#[cfg(windows)]` items
  over 108 lines, both recipes on the host triple, the whole Windows graph type-checking in 26.1 s
  from an empty target directory, and the build script panicking `NotAttempted("llvm-rc")`. The way
  past it is `embed-resource`'s documented `RC_$TARGET` override pointed at GNU windres from
  `binutils-mingw-w64-x86-64`, 6.1 MB fetched against 25 MB for the `llvm-18` that provides
  `llvm-rc`, whose preprocessing would then have wanted a `cl.exe` or a clang as well. The variable
  must name a path and not a program: windres derives its C preprocessor from its own `argv[0]`, so
  an absolute path makes it look for `x86_64-w64-mingw32-gcc` beside itself, fail to find one, and
  fall back to plain `gcc`, while a bare name off `PATH` makes it insist on the prefixed gcc and
  die. The placement question answered itself: the check needs a package, so `check-body` was never
  open to it. Shown able to fail over seven variations of `just check-shell`, three of them faults
  planted in `cfg(windows)` items that the old line passes and the new one fails. Decided in
  [ADR-0011](../../adr/ADR-0011-body-v1.md) decision 11.
- 2026-09-07: what the close opens. The Windows clippy is outside `just check` for one reason, a
  resource step that no argument to `tauri_build::build()` and no environment variable turns off, so
  a `cfg(windows)` regression in the shell still reaches a local commit and is caught in CI rather
  than at the hook. Filed as [R-599](599-the-shells-windows-clippy-waits-on-a-resource-step.md).
