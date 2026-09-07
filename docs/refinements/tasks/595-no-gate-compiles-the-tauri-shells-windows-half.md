# No gate compiles the Tauri shell's Windows half

**Status:** landed 2026-09-07
**Area:** repo-gates
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

Opened 2026-09-07 by the close of
[R-593](593-the-bodys-bind-port-can-be-declared-now-the-shell-compiles.md), whose stated reason for
being actionable was that a constant in the shell is type-checked once the shell is in CI. It is
not, and that is a gap of its own rather than a detail of that entry.

**What the gap is.** `just check-shell` and the CI `shell` job both run
`cargo clippy --locked --all-targets` in `body/app/src-tauri` for the host triple, which is Linux
in both places. Two files there carry six `#[cfg(windows)]` items, about a hundred lines:
`body_server.rs` declares `DEFAULT_BODY_PORT` and `DEFAULT_TOAST_APP_ID` and defines the real
`start` and `exclude_overlay`, and `hotkey.rs` defines the real `register` and `configured_chord`.
The compiler configures every one of them out. `check-body` fmt-checks the shell and rustfmt
follows the module tree without evaluating `cfg`, so those lines are formatted and never
type-checked. The neighbouring crate does not have this hole: `check-body` runs
`cargo clippy --target x86_64-pc-windows-msvc -p os-windows`, which is exactly the missing shape
one directory over ([ADR-0011](../../adr/ADR-0011-body-v1.md)'s second 2026-07-16 addendum).

**What it costs.** A rename, a signature change or a type error inside those items is found on a
Windows box or not at all, and the host sittings that would find it need hardware this repo is not
developed on. `DEFAULT_BODY_PORT` is the worked instance: `scripts/crosscheck.py` reads it as text
on every `just check` and holds 23 far sides to it, and no compiler has ever seen the item.

**Measured 2026-09-07, and it nearly works.**
`cargo clippy --locked --target x86_64-pc-windows-msvc --all-targets -- -D warnings` in
`body/app/src-tauri` type-checks the whole Tauri Windows graph, `webview2-com-sys`, `tao`, the
`windows` crate family and `body-core` among them, and then fails in `cortex-body`'s own build
script: `tauri-winres` panics with `called Result::unwrap() on an Err value: NotAttempted("llvm-rc")`,
which is a resource compiler this host does not have. The rustup toolchains ship `llvm-ar`,
`llvm-cov`, `llvm-objcopy` and a dozen more in `lib/rustlib/x86_64-unknown-linux-gnu/bin` and no
`llvm-rc`, and nothing else on the machine provides one. **The interesting half of that reading is
what it did not need:** no GTK, no webkit, no dbus and no pkg-config shim, because the Linux
desktop stack is not in the Windows dependency graph.

**What would close it.** Get past the resource compiler, then decide where the recipe belongs. The
first is either supplying `llvm-rc` the way `libdbus-1-dev` is supplied here, an `apt-get download`
of an LLVM package unpacked into a userspace prefix, or finding what `tauri-winres` reads to skip
the resource step for a check that never links. The second is the part worth arguing rather than
assuming, and the answer follows from what the first turns out to cost. A check needing no system
library belongs in `check-body` beside the `os_windows` line, inside `just check`, where the
`os_windows` clippy already lives on the same reasoning. A check needing a package cannot go
beside `check-shell`, since
[ADR-0011](../../adr/ADR-0011-body-v1.md)'s 2026-08-25 addendum refuses a second recipe outside the
single gate and AGENTS.md carries that as a rule. Either way, prove it before trusting it the way
the `os_windows` line was proved: a fault planted inside a `cfg(windows)` item is invisible to the
Linux clippy and must fail the new one.

## Trail

- 2026-09-07: opened by the close of
  [R-593](593-the-bodys-bind-port-can-be-declared-now-the-shell-compiles.md), which found that the
  reason that entry gave for being unblocked, a shell constant now being type-checked, does not
  hold for a `cfg(windows)` constant under a Linux clippy.
- 2026-09-07: **landed as a second line inside `check-shell`**, `cargo clippy --locked --target
  x86_64-pc-windows-msvc --all-targets -- -D warnings` in `body/app/src-tauri`, with the CI `shell`
  job installing the target and one more package on the apt line it already runs. Everything this
  entry measured re-derived: six `#[cfg(windows)]` items over 108 lines, both recipes on the host
  triple, the whole Windows graph type-checking in **26.1 s wall from an empty target directory**
  with no GTK, webkit or dbus, and the build script panicking `NotAttempted("llvm-rc")`. The way
  past it is `embed-resource`'s own documented `RC_$TARGET` override pointed at GNU windres from
  `binutils-mingw-w64-x86-64`, 6.1 MB fetched against 25 MB for the `llvm-18` that carries
  `llvm-rc`, whose preprocessing would then have wanted a `cl.exe` or a clang as well. **The
  variable must name a path and not a program**: windres derives its C preprocessor from its own
  `argv[0]`, so an absolute path makes it look for `x86_64-w64-mingw32-gcc` beside itself, fail to
  find one, and fall back to plain `gcc`, while a bare name off `PATH` makes it insist on the
  prefixed gcc and die. The placement question this entry called the part to argue answered itself:
  the check needs a package, so `check-body` was never open to it, and the two clippy lines cover
  complementary halves of the same two files. Proven able to fail over seven arms of `just
  check-shell`, recorded in [ADR-0011](../../adr/ADR-0011-body-v1.md)'s 2026-09-07 addendum, three
  of them faults planted in `cfg(windows)` items that the old line passes and the new one fails.
- 2026-09-07: **what the close opens.** The Windows clippy is outside `just check` for one reason
  only, a resource step that no argument to `tauri_build::build()` and no environment variable
  turns off, so a `cfg(windows)` regression in the shell still reaches a local commit and is caught
  in CI rather than at the hook. Filed as
  [R-599](599-the-shells-windows-clippy-waits-on-a-resource-step.md).
