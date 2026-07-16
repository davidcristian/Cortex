# Repo gates

Deferred refinements for the repo's cross-tree gates, originating in
[ADR-0026](../adr/ADR-0026-prose-style-gates.md) and, for the two Rust trees that no gate
lints, in [ADR-0011](../adr/ADR-0011-body-v1.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed
entries are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** 1 (fmt and clippy for the two Rust trees `just check` never sees)

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
