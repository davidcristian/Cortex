# Repo gates

Deferred refinements for the repo's cross-tree gates, originating in
[ADR-0026](../adr/ADR-0026-prose-style-gates.md), for the two Rust trees that no gate
lints, in [ADR-0011](../adr/ADR-0011-body-v1.md), and for the test-runner mechanics in
[ADR-0002](../adr/ADR-0002-toolchain-gates.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed
entries are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** 3 (`cargo clippy` for the Tauri shell in CI, moved to fix-when-it-bites
2026-07-16; standing test-order randomization, opened as fix-when-it-bites 2026-07-18; the
commit-body wrap gate, opened as fix-when-it-bites 2026-07-18; the
rest landed 2026-07-16, see the outcome note below the verbatim entry)

**Prose style ([ADR-0026](../adr/ADR-0026-prose-style-gates.md)):**
- **Check the commit body's 72-column wrap, not only the header's length.** Opened 2026-07-18,
  fix-when-it-bites, by an audit that measured the drift rather than assumed it.
  [AGENTS.md](../../AGENTS.md) states one width rule for a commit message ("the body explains what
  and why, wrapped at 72"), and `scripts/commitlint.py` enforces `MAX_HEADER_LENGTH = 72` on the
  header alone; nothing looks at the body. Measured over the seven most recent commits at the time:
  every one has body lines past 72, the worst at 77, so the drift is endemic to the tree rather
  than introduced by any one change, which is exactly what an unenforced rule looks like. It is
  cosmetic (`git log` in an 80-column terminal wraps them, it does not truncate) and that is why
  it waits. **What would close it:** one more check in the same walker that already reads every
  line for dashes and volatile references, plus a decision on the exceptions a hard wrap needs,
  which is the whole reason this is not a two-line patch: a URL, a pasted command, a code fence,
  or a `BREAKING CHANGE:` footer can all legitimately exceed 72 and must not be reflowed, and a
  gate that fails on them would be rewriting messages rather than checking them. **Trigger:** the
  first time an over-wide body actually costs something (a message read in a narrow pager or a
  release-note extraction that assumes the wrap), or a deliberate reflow pass over the history,
  after which the gate is what keeps it reflowed. Until then the rule stands as convention, the
  way imperative mood does, and this entry is the record that it is convention rather than gate.

**Test-runner mechanics ([ADR-0002](../adr/ADR-0002-toolchain-gates.md)):**
- **Standing test-order randomization.** Opened 2026-07-18, fix-when-it-bites, by a review that
  found repair reports citing `-p no:randomly` as if it controlled for ordering. `pytest-randomly`
  is not a dependency of the brain workspace or of `scripts/`, so that flag suppresses a plugin
  that was never loaded and every suite has always run in collection order; the citation was a
  gate that could not fail. What replaced it is a real measurement rather than a standing gate:
  the plugin supplied for the run only (`uv run --with pytest-randomly pytest -p randomly
  --randomly-seed=N`), three seeds over `packages/core` (990 tests) plus one over the whole brain
  workspace (1642 tests), all green, with `--collect-only` proving the order genuinely differs
  between seeds. Making it standing is a gate-policy change with real cost: every run would use a
  different order, so reproducing a failure means recovering the seed from the log, and the plugin
  reseeds `random` per test, which changes behaviour for any test that draws. **Trigger:** a test
  that passes alone and fails inside a suite, or any order-dependent flake; the fix is then adding
  `pytest-randomly` to the brain (and `scripts/`) dev dependencies with the seed printed by the
  header it already emits. The `just check` recipes are unchanged for now
  ([ADR-0002 addendum](../adr/ADR-0002-toolchain-gates.md)).

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

  **Reclassified 2026-07-16 to fix-when-it-bites, read against what CI installs and measured.**
  The residual was listed as actionable, but reading what the CI rust job actually provisions
  settled it against wiring. That job (`.github/workflows/ci.yml`) installs no system library
  at all: rust nightly plus stable (rustfmt, clippy, the `x86_64-pc-windows-msvc` target),
  `cargo-llvm-cov`, `just`, `uv`, and `rust-cache`, nothing more; the overlay job is node only
  (its own comment says "npm + jsdom only"). So shell clippy is not a marginal add onto a
  desktop toolchain CI already carries; it introduces a whole new class of CI provisioning. The
  Tauri Linux dev stack (`libwebkit2gtk-4.1-dev` and its transitive deps) has a 630-package
  recursive apt closure (measured with `apt-cache depends --recurse`), an uncacheable
  `apt-get install` that re-runs every job (`rust-cache` caches compiled crates, not apt
  packages), on top of a cold compile of the roughly 150-crate Tauri Rust graph (`wry`,
  `webkit2gtk-sys`, the gtk-rs `-sys` crates, `tauri`). That whole cost lands on `check-body`,
  which every `body/` change runs, to catch the occasional style lint on 881 lines (11 files) of
  host-validated thin wiring. Disproportionate at personal, local-first scale, and the user
  already catches shell clippy on the validation host (that is where the two `collapsible_if`
  were fixed). It moves to fix-when-it-bites with its trigger: **CI gaining the Tauri desktop
  stack for another reason** (a future CI-side Tauri build or smoke job), which drops the
  marginal cost of shell clippy to near zero and lets it ride along; failing that, shell findings
  accumulating faster than the user's local checks catch them, or the shell outgrowing the thin
  wiring the coverage-creep guard already watches. This is a sharpened deferral, still open, so
  the count is unchanged (the same bookkeeping the seam-transport and session-history sharpens
  used), not a decline; the check itself is real, it is only too costly here.
  **Confirmed clippy-clean now.** This host has neither `pkg-config` nor the webkit-dev stack
  (only the `libgtk-3` runtime, no `-dev`, and no sudo), so a permissive `pkg-config` shim stood
  in for it: the `-sys` build scripts consume only link flags, which clippy discards because it
  never links, so a shim that answers every query and version check lets the whole Tauri graph
  type-check. Under it `cargo clippy --all-targets -- -D warnings` on the shell exits 0, and a
  planted `useless_format` makes that exact command exit 101, so the declined check is real
  rather than vacuously green. The heavier note is that assembling even a shim for a one-off
  local check mirrors the CI cost: the stack this host lacks is exactly the stack a CI runner
  would have to install on every shell change.

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
