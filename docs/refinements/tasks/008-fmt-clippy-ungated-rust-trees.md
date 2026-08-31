# cargo fmt and clippy for the ungated Rust trees

**Status:** landed 2026-07-16
**Area:** repo-gates
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)

`just check-body` runs `cargo fmt --all --check` and `cargo clippy --workspace` from `body/`, and
two Rust trees sit outside that workspace by design: the Tauri shell `body/app/src-tauri` (its own
workspace root, `exclude`d so CI needs no webkit or node, ADR-0011 decision 5) and
`crates/os_windows`, which is entirely `cfg(windows)` and so compiles to nothing on the
Linux host and in CI. CI narrows it further: `scripts/ci_paths.py` classifies
`body/app/` as the overlay tree, so a change confined to the shell's Rust runs the node
job and no Rust job at all. Only the unconditional cross-tree scans see either tree: the line
cap and dashcheck always did, and since 2026-08-08 so does the constant scan, which reads the
shell's two default brain endpoints for the seam port it now ties. So the gap is precisely fmt
plus clippy, not the whole gate.
ADR-0011 called this out as a risk ("Windows backend not CI-checked (fmt/clippy/build)")
and accepted it as a cross-platform reality; what the risk left unsaid is that nothing
reports the accumulation, so latent findings collect and are found only when someone
looks. **On 2026-07-16 that is what happened**: an out-of-band check
found five clippy warnings and three files rustfmt would rewrite, none of them regressions
from the work in flight. Two `clippy::collapsible_if` in the shell's `confirm.rs`, three
pedantic findings in `os_windows/src/audio.rs` (one `unused_self`, two
`needless_pass_by_value`), and `cargo fmt` diffs in `confirm.rs`, `converse.rs`, and
`tray.rs`, the last only an import order the 2024 style edition reversed. They were fixed
where they were found, and nothing prevents the next batch from collecting the same way.
The fix splits into two halves of very different cost, which is why it is recorded rather
than folded in. **Format is nearly free for both trees**: `cargo fmt --check` only parses,
needing no system dependency, no extra target, and no build, and it alone would have caught
three of the eight. **Lint is not.** `os_windows` needs a
`rustup target add x86_64-pc-windows-msvc` plus a real `windows`-crate fetch before
`cargo clippy --target x86_64-pc-windows-msvc` can type-check it; that much was proven
from Linux on 2026-07-16 and needs no MSVC toolchain, because clippy never links (a
toolchain-less build, by contrast, is out of reach, so the "build" third of the risk
ADR-0011 named stays host-side). The Tauri shell instead needs the Linux
GTK/webkit/dbus dev packages before its clippy runs at all: an `apt-get install` on a CI
runner, but on this sudo-less WSL host an unpacked `libdbus-1-dev` in a userspace prefix
plus a `pkg-config` shim. Both halves also add a cold Rust build to CI for trees whose
every dependency is otherwise unfetched.
What the refinement does **not** buy: neither tree gains tests or coverage. ADR-0011
excludes both from the coverage gate on purpose (the shell is thin wiring by design, and
the Windows backends are host-validated thin adapters under gate 3), and a cross-target
clippy is a compile check, not a run. This entry is about lint and format only, which is
exactly the class of defect the two trees have been collecting unchecked.

**Landed 2026-07-16 (partial); one clippy residual recorded below.** Reading the entry
against the code sharpened its "fmt plus clippy for both trees" framing into three real gaps
and one non-gap: **`os_windows` fmt was never a gap.** `os_windows` is a member of the `body`
workspace, and `cargo fmt --all --check` (already in `check-body`) formats a member's source
regardless of `cfg`, since rustfmt follows the module tree syntactically and never evaluates
`#[cfg(windows)]`. Proven by injecting a fmt violation into `os_windows/src/audio.rs` and
watching the existing `check-body` fmt step flag it. That is why the eight findings that
prompted this entry included no `os_windows` fmt diff (its three fmt diffs were all in the
shell). What landed:
- **Shell fmt.** `check-body` gained `cd body/app/src-tauri && cargo fmt --check` (the
  excluded shell the workspace `--all` does not reach). Parse only, no build, no extra dep.
- **`os_windows` clippy.** `check-body` gained `cargo clippy --target x86_64-pc-windows-msvc
  -p os-windows`, which type-checks the real `cfg(windows)` code the native `--workspace`
  clippy compiles to nothing. The CI rust job adds the target; clippy never links, so no MSVC
  toolchain. Proven both ways: a `needless_return` in `audio.rs` is not reported by native
  `--workspace` clippy and errors under the windows-target clippy.
- **Classifier.** A shell `.rs` edit used to gate only the node overlay job (`body/app/` →
  overlay). `body/app/src-tauri/` now classifies as **rust** (a rule ordered before
  `body/app/`), so a shell change gates the rust job that runs the shell fmt. Without this the
  fmt gate could not fire on the change that breaks it. `os_windows` already gated rust.
Runtime cost added to CI: one cold windows-target build of `body-core` + `os-windows` (the
`windows` crate fetch), cached by `rust-cache` thereafter; the shell fmt adds no build.

## Trail

- 2026-07-16: Opened when the two Rust trees `just check` never lints turned out to have been
  collecting findings unchecked, taking the area from zero entries back to one. An out-of-band check
  found five clippy warnings and three files rustfmt would rewrite, none of them regressions from
  the work in flight. The index notes that this entry originates in ADR-0011 rather than the
  ADR-0026 the area doc was extracted under.
- 2026-07-16: Landed partially later the same day, the count holding at one. Shell fmt and the
  `os_windows` windows-target clippy went into `check-body`, and the CI classifier gained a rule
  so a shell `.rs` edit gates the rust job. The pass also found `os_windows` fmt had never been a
  gap, a workspace member being formatted regardless of `cfg`. The residual, shell clippy in CI,
  is recorded as its own entry.
