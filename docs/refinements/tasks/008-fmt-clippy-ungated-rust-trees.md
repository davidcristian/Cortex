# cargo fmt and clippy for the two unchecked Rust trees

**Status:** done 2026-07-16
**Area:** repo-checks
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

`just check-body` runs `cargo fmt --all --check` and `cargo clippy --workspace` from `body/`, and
two Rust trees sit outside that workspace by design: the Tauri shell `body/app/src-tauri` (its own
workspace root, excluded so CI needs no webkit or node) and `crates/os_windows`, which is entirely
`cfg(windows)` and so compiles to nothing on the Linux host and in CI. CI narrowed it further:
`scripts/ci_paths.py` classified `body/app/` as the overlay tree, so a change confined to the
shell's Rust ran the node job and no Rust job. Only the unconditional cross-tree scans read either
tree. ADR-0011 accepted the risk, but nothing reported what accumulated behind it.

On 2026-07-16 a check outside the usual run found five clippy warnings and three files rustfmt
would rewrite, none of them caused by the work in flight: two `clippy::collapsible_if` in the
shell's `confirm.rs`, three pedantic findings in `os_windows/src/audio.rs` (one `unused_self`, two
`needless_pass_by_value`), and fmt differences in `confirm.rs`, `converse.rs` and `tray.rs`, the
last only an import order the 2024 style edition reversed.

The two halves cost very differently. Format is nearly free for both trees, since
`cargo fmt --check` only parses: no system dependency, no extra target, no build, and it alone
would have caught three of the eight findings. Lint is not. `os_windows` needs
`rustup target add x86_64-pc-windows-msvc` and a real `windows`-crate fetch before
`cargo clippy --target x86_64-pc-windows-msvc` can type-check it, proven from Linux on 2026-07-16
and needing no MSVC toolchain because clippy never links. The Tauri shell needs the Linux
GTK/webkit/dbus dev packages before its clippy runs at all. Neither tree gains tests or coverage
from any of this; a cross-target clippy is a compile check, not a run.

Partly closed the same day. Reading the entry against the code turned "fmt plus clippy for both
trees" into three real gaps and one that was never a gap: `os_windows` fmt was already covered,
because it is a member of the `body` workspace and `cargo fmt --all --check` formats a member's
source regardless of `cfg`, rustfmt following the module tree without evaluating
`#[cfg(windows)]`. Proven by injecting a fmt violation into `os_windows/src/audio.rs` and watching
the existing step report it, which is why the eight findings included no `os_windows` fmt
difference. What was added:

- Shell fmt: `check-body` gained `cd body/app/src-tauri && cargo fmt --check`, which the workspace
  `--all` does not reach. Parse only, no build, no extra dependency.
- `os_windows` clippy: `check-body` gained `cargo clippy --target x86_64-pc-windows-msvc -p
  os-windows`, which type-checks the real `cfg(windows)` code that the native `--workspace` clippy
  compiles to nothing. The CI rust job adds the target. Proven both ways: a `needless_return` in
  `audio.rs` is not reported by native `--workspace` clippy and errors under the windows-target
  clippy.
- Classifier: `body/app/src-tauri/` now classifies as rust, in a rule ordered before `body/app/`,
  so a shell `.rs` edit runs the rust job that runs the shell fmt. Without it the new check could
  not fire on the change that breaks it.

Added CI cost: one cold windows-target build of `body-core` and `os-windows`, cached by
`rust-cache` afterwards. The shell fmt adds no build. Shell clippy in CI is left over as
[R-009](009-shell-clippy-in-ci.md).

## History

- 2026-07-16: Opened when the two Rust trees `just check-body` never lints turned out to have been
  accumulating findings: five clippy warnings and three files rustfmt would rewrite, none of them
  caused by the work in flight.
- 2026-07-16: Partly closed later the same day. Shell fmt and the `os_windows` windows-target
  clippy went into `check-body`, and the CI classifier gained a rule so a shell `.rs` edit runs the
  rust job. The pass also found `os_windows` fmt had never been a gap, a workspace member being
  formatted regardless of `cfg`. The residue, shell clippy in CI, is its own entry.
