# Repo gates

Deferred refinements for the repo's cross-tree gates, originating in
[ADR-0026](../adr/ADR-0026-prose-style-gates.md) and, for the two Rust trees that no gate
lints, in [ADR-0011](../adr/ADR-0011-body-v1.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed
entries are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** 1 (`cargo clippy` for the Tauri shell in CI; the rest landed 2026-07-16, see
the outcome note below the verbatim entry)

**Gate coverage ([ADR-0011](../adr/ADR-0011-body-v1.md)):**
- **`cargo fmt` and `cargo clippy` for the two ungated Rust trees.** `just check-body` runs
  `cargo fmt --all --check` and `cargo clippy --workspace` from `body/`, and two Rust trees
  sit outside that workspace by design: the Tauri shell `body/app/src-tauri` (its own
  workspace root, `exclude`d so CI needs no webkit or node, ADR-0011 decision 5) and
  `crates/os_windows`, which is entirely `cfg(windows)` and so compiles to nothing on the
  Linux host and in CI. CI narrows it further: `scripts/ci_paths.py` classifies
  `body/app/` as the overlay tree, so a change confined to the shell's Rust runs the node
  job and no Rust job at all. Only the two unconditional cross-tree scans (the line cap and
  dashcheck) see either tree, so the gap is precisely fmt plus clippy, not the whole gate.
  ADR-0011 called this out as a risk ("Windows backend not CI-checked (fmt/clippy/build)")
  and accepted it as a cross-platform reality; what the risk left unsaid is that nothing
  reports the accumulation, so latent findings pile up silently and are only ever noticed
  by someone happening to look. **On 2026-07-16 that is what happened**: an out-of-band check
  found five clippy warnings and three files rustfmt would rewrite, none of them regressions
  from the work in flight. Two `clippy::collapsible_if` in the shell's `confirm.rs`, three
  pedantic findings in `os_windows/src/audio.rs` (one `unused_self`, two
  `needless_pass_by_value`), and `cargo fmt` diffs in `confirm.rs`, `converse.rs`, and
  `tray.rs`, the last only an import order the 2024 style edition reversed. They were fixed
  where they were found; the next batch has nothing stopping it.
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
  exactly the class of defect the two trees have been quietly collecting.

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
    excluded shell the workspace `--all` cannot see). Parse only, no build, no extra dep.
  - **`os_windows` clippy.** `check-body` gained `cargo clippy --target x86_64-pc-windows-msvc
    -p os-windows`, which type-checks the real `cfg(windows)` code the native `--workspace`
    clippy compiles to nothing. The CI rust job adds the target; clippy never links, so no MSVC
    toolchain. Proven both ways: a `needless_return` in `audio.rs` is invisible to native
    `--workspace` clippy and errors under the windows-target clippy.
  - **Classifier.** A shell `.rs` edit used to gate only the node overlay job (`body/app/` →
    overlay). `body/app/src-tauri/` now classifies as **rust** (a rule ordered before
    `body/app/`), so a shell change gates the rust job that runs the shell fmt. Without this the
    fmt gate could not fire on the change that dirties it. `os_windows` already gated rust.
  Runtime cost added to CI: one cold windows-target build of `body-core` + `os-windows` (the
  `windows` crate fetch), cached by `rust-cache` thereafter; the shell fmt adds no build.
- **`cargo clippy` for the Tauri shell in CI (the residual).** The shell's clippy still runs
  nowhere in CI. Unlike the shell's fmt (parse only) and `os_windows`'s clippy (a target add,
  no link), shell clippy needs the shell to actually compile: the Linux GTK/webkit/dbus dev
  packages (`apt-get install` on a runner; on this sudo-less WSL host an unpacked
  `libdbus-1-dev` in a userspace prefix plus a `pkg-config` shim) and a cold Tauri build with
  webkit. That build cost is why it is not folded into `check-body`, which every `body/` change
  runs. It is the one half of this entry that still lets a shell clippy finding accumulate
  unseen (two `collapsible_if` did, in `confirm.rs`, before 2026-07-16). The toolchain-linked
  full build of either tree stays host-side, as ADR-0011 already notes.

**Repo gates ([ADR-0026](../adr/ADR-0026-prose-style-gates.md)):**
- **The fail-open `scripts/` gate config closed 2026-07-12
  ([ADR-0026 addendum](../adr/ADR-0026-prose-style-gates.md)).** `scripts/pyproject.toml`
  enumerated the modules it measured, once in the pytest `--cov=` list and again in
  pyright's `include`; adding `dashcheck.py` silently escaped BOTH the 100% coverage gate
  and strict typing until the omission was spotted by eye (the tree still reported 100%,
  because a module nobody measures cannot lower the average). Both now measure the tree
  rather than a list: `--cov=.` with an explicit coverage omit for `tests/` and `.venv/`
  (test files stay unmeasured, as before), and a pyright `include` of `"."` with an
  explicit exclude. A new script is gated by default; escaping needs a written exclusion.
  Proven to fail on an unlisted probe script (coverage 98.62% + two strict pyright
  errors) before being trusted.
