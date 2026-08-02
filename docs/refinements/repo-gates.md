# Repo gates

Deferred refinements for the repo's cross-tree gates, originating in
[ADR-0026](../adr/ADR-0026-prose-style-gates.md), for the two Rust trees that no gate
lints, in [ADR-0011](../adr/ADR-0011-body-v1.md), for the test-runner mechanics in
[ADR-0002](../adr/ADR-0002-toolchain-gates.md), and for the cross-language constant
registry in [ADR-0029](../adr/ADR-0029-vision-screen-capture.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed
entries are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** 5 (`cargo clippy` for the Tauri shell in CI, moved to fix-when-it-bites
2026-07-16; standing test-order randomization, opened as fix-when-it-bites 2026-07-18; the three
exceptions the wrap gate did not ship, opened as fix-when-it-bites 2026-07-19 behind the landing
of the commit-body wrap check itself; the overlay stylesheet outside the line cap, opened as
fix-when-it-bites 2026-08-03 behind the cap reaching the overlay's TypeScript; the couplings the
cross-language constant scan does not hold yet, opened as fix-when-it-bites 2026-08-03 behind
that scan landing; the rest landed 2026-07-16, 2026-07-19 and 2026-08-03, see the outcome notes
below the verbatim entries)

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

  **Landed 2026-07-19, with one of the four exceptions this entry called the actual design
  ([ADR-0026 wrap addendum](../adr/ADR-0026-prose-style-gates.md)).** `scripts/commitlint.py` now
  measures every line below the header against a new `MAX_BODY_WIDTH = 72`, inside the same walker
  that already read each line for dashes and volatile references, exactly as the entry predicted;
  the header keeps `check_header`'s own cap so one long subject is one complaint rather than two.
  The exception that shipped is `too_wide`: a line past the wrap whose longest word alone exceeds
  it has nowhere to break, so a URL, a path, or a long identifier is exempt, while ordinary prose
  past the wrap is not. Proven against the four 73-character lines that had already reached master
  (flagged with their line numbers and widths) and against the wrapped bodies it must pass. The
  drift the entry measured is therefore gated rather than convention, and the trigger it waited
  for turned out not to be what moved it: the rule was enforced because a slice's own predecessor
  had recorded the same ungated rule as a defect, not because a narrow pager finally cost
  something. What the landing did **not** decide is the rest of the exception design, which is the
  residual below.
- **The three exceptions the wrap gate did not ship (opened 2026-07-19 behind the landing).**
  *Fix when it bites.* The entry above named four things a hard wrap must not touch, a URL, a
  pasted command, a fenced code block, and a `BREAKING CHANGE:` footer, and called deciding them
  "the whole reason this is not a two-line patch". Only the first is covered, because the shipped
  exemption is a property of the longest **word** rather than of the line's **kind**, and a pasted
  command or a fenced line is built out of ordinary short words. Measured against the shipped gate
  on 2026-07-19 rather than reasoned about: one message carrying an indented
  `docker compose --project-directory . -f docker/docker-compose.yml ... up -d` line (108 chars,
  longest word 29), a fenced `uv run pytest packages/core --cov ...` line (82 chars), and a
  `BREAKING CHANGE:` footer of short words (118 chars) drew three complaints and exit 1. The
  footer is the sharp one, because [AGENTS.md](../../AGENTS.md) itself mandates that footer for a
  breaking change, so the gate can now refuse a message the commit rules require; it is also the
  easiest of the three to live with, since a footer is prose and its value may legitimately carry
  newlines, so it can simply be wrapped. A command and a fence cannot: reflowing either changes
  what it says, which is the "rewriting messages rather than checking them" failure the entry
  named. **What would close it:** a line-kind exemption rather than a word-width one, which is a
  fence toggle carried through the walk plus a heuristic for a pasted command (a leading indent, a
  shell prompt), and the decision about whether a footer is exempt at all or simply wrapped like
  any other prose. **Trigger:** the first commit that genuinely needs a command or a block in its
  body, at which point the author chooses between mangling the paste and bypassing the hook, which
  is precisely the outcome the entry above was recorded to avoid. Until then the gate is right
  about every message this repo has actually written.

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

**Gate reach ([ADR-0011](../adr/ADR-0011-body-v1.md) line-cap addendum):**
- **The line cap did not cover the overlay at all, and had not since the overlay was gated.**
  Found 2026-08-03 while reviewing a landed change, and recorded here because a gate that cannot
  fail is a defect in its own right, whatever it happens to have missed. `scripts/linecap.py` held
  `SOURCE_SUFFIXES = {".py", ".rs"}` from the day it was written, which was correct then:
  [ADR-0001](../adr/ADR-0001-architecture.md) open question 6 scoped both the coverage gate and the
  300-line cap to `.py`/`.rs` while the overlay was "kept minimal". ADR-0011's 2026-07-01 addendum
  reversed that for coverage and said so; nothing reversed it for the cap, and nothing noticed,
  because the gate kept passing. **How long, and what it let through:** thirty-three days from the
  overlay's first gated component to 2026-08-03, over a tree that reached 107 TypeScript files, 65
  of them the non-test sources the cap would have been measuring the whole time.
  Two entries in [body-overlay.md](body-overlay.md) tracked cap violations by eye over that window
  and both drifted. `bridge/demoBridge.ts` was recorded at 326 on the day it already stood at 351,
  and it was still 351 fourteen days later; `overlay/panelPlacement.ts` crossed the cap the day
  after the entry that called demoBridge the only one over it, reached 371, and sat there for
  thirteen days until an unrelated ResizeObserver change took it to 295 by accident. Neither the
  false claim nor the stale number cost anything beyond themselves, which is the point: the failure
  of an unenforced rule is silent by construction, and it was found by a review rather than by a
  gate. **Landed the day it was found**, so this entry is a record rather than a deferral: the scan
  now covers `.ts`/`.tsx`, `demoBridge.ts` was split rather than exempted, and the whole decision
  including what stays outside the cap is in the ADR-0011 line-cap addendum. Proven able to fail
  before being trusted, planted file by planted file, per the same distrust-green rule that turned
  this up.
- **The overlay's stylesheet is outside the line cap.** *Fix when it bites.* Opened 2026-08-03
  behind the entry above, because turning the cap on made the exclusion a decision rather than an
  oversight. `body/app/src/overlay.css` is **2420 lines**, by a wide margin the longest hand-written
  file in the repo, and no gate measures it. It is excluded on the argument that the cap's remedy is
  "split by responsibility", which presumes a module with a public contract, while a stylesheet is
  one cascade whose ordering is load-bearing: splitting it trades a long file for `@import` ordering
  that nothing checks and that fails visually rather than loudly. That argument is honest about the
  remedy and evasive about the problem, since 2420 lines is exactly the cognitive load the cap
  exists to bound, and the file has grown with every overlay slice. **What would close it:** either
  a cap for `.css` at a width chosen for stylesheets rather than modules, with the split done by
  layer (tokens, panel, console, motion) and imported in a fixed order from one entry sheet, or the
  same split done for its own sake with the cap following. Neither is a scanner change; the scanner
  needs one suffix added. **Trigger:** the first time an edit lands in the wrong cascade position
  because the file is too long to hold in view, or a second stylesheet appearing, at which point the
  ordering question has to be answered anyway. Until then the cap covers every executable module in
  the repo and this is the one measured hole in it.

**Cross-language constants ([ADR-0029](../adr/ADR-0029-vision-screen-capture.md)
cross-language-constant addendum):**
- **The couplings `crosscheck.py` deliberately does not hold yet.** *Fix when it bites.* Opened
  2026-08-03 behind the scan landing, because a registry with two entries makes every unregistered
  coupling a decision rather than an absence. A survey of the whole seam on that day, run before
  the registry was written rather than after, found the rest, and they fall into three kinds that
  need three different answers. **First, relations the comparator cannot express.** The scan
  compares for equality, and three real couplings are orderings: the body's `MAX_EDGE_CEILING`
  (4096) must stay at or below the brain's `MAX_IMAGE_EDGE` (8192), the body's `CAPTURE_MIME`
  must stay inside the brain's `ALLOWED_MIME_TYPES`, and `cortex_body_client`'s
  `MAX_RECEIVE_BYTES` (16 MiB) must stay above both byte ceilings. Each would need a comparator
  and a registry field naming which one applies, which is a design, not a line.
  **Second, copies that are not declarations.** A value spelled inside a string is invisible to a
  scan that reads constant declarations: `docker/docker-compose.yml`'s healthcheck carries
  `x-cortex-seam-token` inline in a one-line Python command (a fourth copy of a key the gate now
  ties in three places, and the one whose drift would be silent), the brain's port `50051` lives
  in the shell as `"http://127.0.0.1:50051"` against `SeamServerConfig.port`, and the body's bind
  port `50151` is a bare literal argument in `body_server.rs` against a compose env var. Teaching
  a constant scanner to read a shell string embedded in YAML is a different tool. **Third,
  TypeScript, which the scan has no declaration syntax for at all.** The overlay matches wire
  values by hand: `CAPTURE_SCREEN_TOOL` against the brain's `CAPTURE_SCREEN_TOOL_NAME`, whose
  drift leaves the capture dot unlit, and a bare `"thinking"` literal (in `turnState.ts` and
  twice in `Message.tsx`) against `THINKING_STATE`, whose drift leaves the reasoning trace
  unaccumulated and its chip unstyled. Both fail silently, by a surface simply never appearing.
  Adding `.ts` to `DECLARATIONS` is one pattern; deciding that a bare literal must first become
  a named constant is the actual work. **A fourth kind arrived on 2026-08-03 and is the same
  entry rather than a new one:** a name that crosses from TypeScript into CSS, where the far side
  is a USE and not a declaration at all, so there is nothing for a declaration scanner to compare.
  `overlay/panelBudget.ts` publishes `CEILING_PROPERTY` (`--ceiling`) and overlay.css spends it as
  `var(--ceiling, 100vh)`; rename either side and the fallback quietly becomes the viewport, which
  is the uncapped section the panel's budget exists to stop, with every test still green
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md), the 2026-08-03 budget addendum). The same
  shape already holds `data-resizing`, written by the placement and read only by the rule that
  hides the history's thumb. Both are pinned as literals in their own suites, which is what a
  rename has to walk past; what would close it is a scan that reads a stylesheet for uses rather
  than a source for declarations.
  **One of them is already divergent, which is why this is recorded rather than folded in.**
  `TITLE_MAX` is 48 in `brain/packages/core/src/cortex_core/sessions.py` and 32 in
  `body/app/src/overlay/sessionState.ts`, and the comment above the brain's declaration says the
  overlay "applies the same rule and is kept documented in step, since neither side can see the
  other's constant". It does not, and
  [ADR-0021](../adr/ADR-0021-session-read-seam.md) records the artefact (a first
  message of 33 to 48 characters reads longer in the switcher than in the header). Registering
  that pair today would make the gate red on a shipped disagreement nobody has decided how to
  resolve, and turning a gate on over an unresolved divergence is how a gate gets bypassed. So
  the pair waits on the decision, not on the scan. **What would close it:** a comparator field
  for the ordered relations, a `.ts` declaration syntax, and a resolution for `TITLE_MAX` (one
  number, or an ADR saying the two bounds are deliberately different). **Trigger:** the first
  coupling that actually drifts, or the `TITLE_MAX` decision being made for its own reasons, at
  which point registering the pair costs three lines.

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
