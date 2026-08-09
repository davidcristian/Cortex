# Repo gates

Deferred refinements for the repo's cross-tree gates, originating in
[ADR-0026](../adr/ADR-0026-prose-style-gates.md), for the two Rust trees that no gate
lints, in [ADR-0011](../adr/ADR-0011-body-v1.md), for the test-runner mechanics in
[ADR-0002](../adr/ADR-0002-toolchain-gates.md), and for the cross-language constant
registry in [ADR-0029](../adr/ADR-0029-vision-screen-capture.md). Extracted from the ROADMAP's
deferred-refinements section on 2026-07-15 with the entries kept verbatim; landed
entries are the historical record of what each deferral became, and the index at
[index.md](index.md) carries the recommended pickup order.

**Open items:** 6 (`cargo clippy` for the Tauri shell in CI, moved to fix-when-it-bites
2026-07-16; standing test-order randomization, opened as fix-when-it-bites 2026-07-18; the three
exceptions the wrap gate did not ship, opened as fix-when-it-bites 2026-07-19 behind the landing
of the commit-body wrap check itself; the overlay stylesheet outside the line cap, opened as
fix-when-it-bites 2026-08-03 behind the cap reaching the overlay's TypeScript; the three
couplings the widened constant scan still cannot hold, opened as fix-when-it-bites 2026-08-08
when four of the five kinds its predecessor named were closed, which is the backlog working as
intended rather than a count standing still, and grown to four the same day by the gRPC status
codes the kinded body-gateway error currency now needs both sides to spell alike, folded into
that entry rather than counted beside it, and still four on 2026-08-09 by exchange, the roll's
duration closing onto a `--roll` custom property the sheet spells once and the spend side of a
value-declaring property taking its place, folded in the same way; and the sixth, added 2026-08-08 by the turn-cost run
that moved the recall default, whose harness never entered the repo, so the one measurement in
that ADR that names no reproducing test is also the one whose result shipped, sharpened the same
day when its trigger fired and the fold-under-load run committed a seam-spanning driver: placement
and corpus seeding are settled by that second instance, and what is left is the two halves only a
driver going over gRPC meets, an arm that needs the container restarted and a result reported as an
interval. The compose bind
default that lands in the repo tree came off this list on 2026-08-08, ahead of its own trigger, as
a fourth cross-tree scan whose rule is three-way rather than the one this entry sketched; a mention
counting nothing came off it on 2026-08-09, on its trigger, as an opt-in exact occurrence count,
and it is the one close that leaves this number where it found it, having been appended on
2026-08-08 without ever being added to this list; the rest
landed 2026-07-16, 2026-07-19, 2026-08-03 and 2026-08-06, the last of them the live pgvector run
sharing the brain's `memories` table, closed ahead of its trigger rather than by it,
see the outcome notes below the verbatim entries)

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
- **The live contract runs shared the brain's own Redis keyspace.** Found and closed the same
  day, 2026-08-03, so it is recorded here as what it was rather than as work waiting. This is not
  a new deferral so much as an old one that had been mis-sized: the
  [ADR-0021 sweep addendum](../adr/ADR-0021-session-read-seam.md) recorded on 2026-07-14 that the
  live session checks read a fixed recency window with fixture dates in the past, so real sessions
  more recent than those crowd them out, and it sized the residual against a `limit=50` window,
  meaning fifty real sessions before it would bite. Two days later the pinning addendum landed a
  `limit=3` check on the same assumption and the trigger silently fell from fifty to three; the
  residual was not resized, and the entry in
  [session-read-seam.md](session-read-seam.md) still carried the fifty. So it had been latent
  since 2026-07-16 and failing in practice since the compose Redis first held three real sessions
  dated after the fixtures, which its oldest surviving one puts at 2026-07-21 or earlier: roughly
  a fortnight of a live run that would have blamed a correct adapter, unnoticed because these
  suites are run by hand. Reproduced on 2026-08-03 with sixteen real sessions present. **What it
  became:** the live runs select a Redis logical database of their own
  (`brain/packages/session/tests/live_redis.py`, database 15, which production never selects) and
  empty it before the suite and after every check, so every check starts from the empty store the
  fakeredis fixture already gives it. That also closed two siblings of the same defect wearing the
  other mask: the schedule and handoff live suites used to **skip** whenever the shared database
  held a real record, reporting green while asserting nothing, and both skips are gone because
  there is nothing real in that database to protect. The prefix sweeps went with them, and with
  them a coupling that restated each adapter's key layout inside the test. Decision, rejected
  alternatives, and evidence in the
  [ADR-0002 addendum on the live-run database](../adr/ADR-0002-toolchain-gates.md). The lesson
  worth keeping is the one this entry is filed under: a recorded residual is sized against the
  code that existed when it was written, and a later change can lower its trigger without anyone
  reading it again.
- **The live pgvector run still shares the brain's `memories` table.** *Fix when it bites.*
  Opened 2026-08-03 behind the Redis fix above, which does not reach it: Postgres isolation is a
  different mechanism, a dedicated database or a schema plus a `search_path`, with
  `docker/postgres/init.sql` applied to it, so it is its own piece of work rather than one more
  line in the same helper. The exposure is real and was measured, not assumed:
  `memory_contract.check_empty_search` asserts `search(k=5) == []` over the whole table and
  `check_ranks_by_similarity` asserts an exact top-2, so with Postgres up and the table empty the
  suite passes, and inserting a single real (non `contract-`) memory row reddens
  `check_empty_search` at `memory_contract.py:36` with no code changed. It waits because the table
  is empty on this machine today, so the suite is currently honest, and because the two checks
  that need the whole table could alternatively be re-derived to assert within a `contract-` scope
  (`search(..., scopes=[...])` already exists), which is a smaller change that trades some of the
  contract's reach for it. **Trigger:** the first live memory run on a machine that has actually
  remembered something, or any pgvector failure whose first suspect should be
  `select count(*) from memories where id not like 'contract-%'`. Recorded at the module doc
  ([brain-memory.md](../modules/brain-memory.md)) and in its runbook
  ([memory-pgvector.md](../runbooks/memory-pgvector.md)) so the failure is legible when it lands.

  **Landed 2026-08-06 ([ADR-0002 addendum on the live pgvector database](../adr/ADR-0002-toolchain-gates.md)),
  ahead of its trigger rather than by it.** What moved it was two pieces of work queued behind it
  rather than a failure: the judge reranker's cost fell twentyfold, so a memory-enabled deployment
  that actually remembers things stopped being hypothetical, and the widened recall corpus that
  decides that default would have put the first real rows in the table. The entry's own measurement
  was reproduced before anything was changed, exactly as written: one real memory row turned
  `check_empty_search` red at `memory_contract.py:36`. **What it became:** the live run opens the
  `cortex_contract` database (`brain/packages/memory/tests/live_postgres.py`, the Postgres twin of
  `live_redis.py`, rewriting the DSN's path where that one rewrites the database index and calling
  `TRUNCATE TABLE memories` where that one calls `FLUSHDB`), emptied before the suite and after
  every check, and `docker/postgres/live-contract-db.sql` bootstraps it through the compose by
  including `init.sql` rather than restating the schema. The alternative this entry named,
  re-deriving the two whole-table checks inside a `contract-` scope, was not taken: it narrows what
  the contract proves in order to survive a shared table, and the whole point of a suite the fake
  and the real adapter both pass is that they pass the same checks. The schema-plus-`search_path`
  option was rejected on its failure mode, since the adapter's SQL is unqualified and a
  `search_path` that fails to apply lands the suite, its `TRUNCATE` included, on the brain's own
  table in silence. A machine whose data dir predates the bootstrap file gets a run that refuses to
  start, naming the two statements that create the database, rather than one that quietly connects
  elsewhere. Proven with a real row sitting in the brain's table: the suite passes, that table is
  byte-identical across the run, and all four refusals were fired before being trusted.
- **The end-to-end turn-cost harness never entered the repo.** *Fix when it bites.* Opened
  2026-08-08 by the run that moved `CORTEX_MEMORY_RECALL` to `judge`
  ([ADR-0038 turn-cost addendum](../adr/ADR-0038-ranked-recall.md)). It is filed here rather than
  in [memory.md](memory.md) because what is unresolved is where a driver that spans the seam lives
  and how it is run, which is what this section is about, while the recall entry the measurement
  served closed the same day and left nothing open about recall. Every other measurement in that
  ADR names an `integration`-marked test that reproduces it
  (`packages/inference/tests/test_rerank_judge_wide_live.py`, `test_history_recap_live.py`,
  `test_session_title_live.py`); the turn-cost numbers name none. What produced them was a
  host-side Python client that opened one `Converse` stream per turn against the brain's
  `BrainService`, timed the first `TextDelta` and the `TurnComplete`, and ran three blocks of 48
  turns in A/B/A order with a container restart between them, and it lived in a scratchpad, so the
  published 0.515 s of time to first token is a figure nobody can re-derive without rebuilding the
  driver from that addendum's prose. **The stated reason for punting was that a driver spanning the
  seam is not an adapter test and wanted its own decision about where such a thing belongs, and
  reading the tree afterwards makes that decision smaller than the punt implied:**
  `packages/orchestrator/tests/test_schedule_live_seam.py` already is one, an `integration`-marked
  host-side client that drives the shipped `BrainServiceStub` against the compose stack and cleans
  up after itself, so the placement question has a precedent and the answer is probably
  `packages/orchestrator/tests/`. What has no precedent is the rest of the shape: a measurement
  restarts containers between arms with one environment variable changed, pre-seeds a corpus into a
  session scope, and reports a distribution with a confidence interval rather than asserting a
  bound, none of which a pytest case expresses well, and a committed one would still have to decide
  whether the A/B/A control arm is part of the test or part of a runbook. **Trigger:** the next
  end-to-end measurement of a whole turn (a vision turn, a tool turn, a handoff), which would
  otherwise pay the same build cost again, or any challenge to the shipped recall default that
  needs the run reproduced rather than cited.
- **The trigger fired 2026-08-08 and the entry stays open, narrower
  ([ADR-0038 fold-under-load addendum](../adr/ADR-0038-ranked-recall.md)).** The fold-under-load
  measurement is the next end-to-end run of a whole turn, and it committed its driver rather than
  leaving it in a scratchpad: `packages/orchestrator/tests/test_fold_under_load_live.py`,
  `integration`-marked, in the directory this entry guessed. **Two thirds of what it named as
  unresolved are settled by that second instance.** Placement is no longer a guess, since
  `test_schedule_live_seam.py` and this one now sit beside each other doing the same kind of thing;
  and pre-seeding a corpus into a session scope has a shape, which is writing through the real
  `RedisSessionStore` under test-owned session ids and deleting them in a `finally`, exactly the
  schedule test's own discipline. **The rest is untouched, and the reason is a distinction this
  entry did not draw.** A measurement whose subject lives INSIDE the brain process is better driven
  in-process than across the wire: the fold run had to timestamp a lock, so it wired the real
  adapters and drove the shipped `converse` generator directly, which let it change an arm by
  constructing a config rather than by restarting a container, and let it read the thing being
  measured at all. So it never met the two hard parts. **What is still unresolved is therefore
  narrower and better named:** how a committed test expresses an arm that needs the brain container
  restarted with one environment variable changed (which only a driver going over gRPC ever needs),
  and how one reports a distribution with an interval rather than asserting a bound, the
  fold run having reported numbers and asserted only invariants that hold whatever the model says.
  The A/B/A question is the same one in different clothes: a control arm that is another
  container configuration belongs wherever the restart belongs. **Trigger unchanged**, minus the
  half this run answered: the next measurement that genuinely needs a differently-configured brain
  container between arms, or a challenge to the shipped recall default.

**Gate coverage ([ADR-0011](../adr/ADR-0011-body-v1.md)):**
- **`cargo fmt` and `cargo clippy` for the two ungated Rust trees.** `just check-body` runs
  `cargo fmt --all --check` and `cargo clippy --workspace` from `body/`, and two Rust trees
  sit outside that workspace by design: the Tauri shell `body/app/src-tauri` (its own
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
  oversight. `body/app/src/overlay.css` was **2420 lines** the day this opened and is **2686** as of
  2026-08-08, by a wide margin the longest hand-written file in the repo, and no gate measures it. It is excluded on the argument that the cap's remedy is
  "split by responsibility", which presumes a module with a public contract, while a stylesheet is
  one cascade whose ordering is load-bearing: splitting it trades a long file for `@import` ordering
  that nothing checks and that fails visually rather than loudly. That argument is honest about the
  remedy and evasive about the problem, since a file this long is exactly the cognitive load the cap
  exists to bound, and it has grown with every overlay slice, by 266 lines since the entry was
  filed. That growth is also why the number above is now measured rather than quoted: an entry that
  states a file's size has to re-read the file, the way every other claim about the code here does. **What would close it:** either
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
  TypeScript, which the scan had no declaration syntax for at all. That half closed the same day
  (below), so what remains of this kind is the naming, not the scanning.** The overlay matches wire
  values by hand: `CAPTURE_SCREEN_TOOL` against the brain's `CAPTURE_SCREEN_TOOL_NAME`, whose
  drift leaves the capture dot unlit, and a bare `"thinking"` literal (in `turnState.ts` and
  twice in `Message.tsx`) against `THINKING_STATE`, whose drift leaves the reasoning trace
  unaccumulated and its chip unstyled. Both fail silently, by a surface simply never appearing.
  `CAPTURE_SCREEN_TOOL` is now registrable as it stands, at the cost of a registry entry; the
  `"thinking"` literals are not, and deciding that a bare literal must first become a named
  constant is the work that is left. **A fourth kind arrived on 2026-08-03 and is the same
  entry rather than a new one:** a name that crosses from TypeScript into CSS, where the far side
  is a USE and not a declaration at all, so there is nothing for a declaration scanner to compare.
  `overlay/panelBudget.ts` publishes `CEILING_PROPERTY` (`--ceiling`) and overlay.css spends it as
  `var(--ceiling, 100vh)`; rename either side and the fallback quietly becomes the viewport, which
  is the uncapped section the panel's budget exists to stop, with every test still green
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md), the 2026-08-03 budget addendum). The same
  shape already holds `data-resizing`, written by the placement and read only by the rule that
  hides the history's thumb, and gained two more members later the same day: `overlay/measured.ts`
  publishes `CHAT_FLOOR_PROPERTY` (`--chat-floor`) and `TRACE_ROW_PROPERTY` (`--trace-row`), spent
  by `.log`'s floor and by the settled Thoughts disclosure, where a rename on either side falls back
  to the value declared on `:root` and so degrades to exactly the frozen constants the probe
  replaced, silently and with every test green ([ADR-0035](../adr/ADR-0035-console-and-motion.md),
  the 2026-08-03 chat-floor addendum). All four are pinned as literals in their own suites, which is
  what a rename has to walk past; what would close it is a scan that reads a stylesheet for uses
  rather than a source for declarations.
  **One of them was already divergent, which is why this was recorded rather than folded in, and
  that one is settled and registered as of 2026-08-03 (the same day, later).** `TITLE_MAX` was 48
  in `brain/packages/core/src/cortex_core/sessions.py` and 32 in
  `body/app/src/overlay/sessionState.ts`, and the comment above the brain's declaration said the
  overlay "applies the same rule and is kept documented in step, since neither side can see the
  other's constant". It did not. This entry's framing of the artefact, taken from
  [ADR-0021](../adr/ADR-0021-session-read-seam.md), was also narrower than the code: it named the
  chat being loaded, where the header-title carry had already closed the gap, and the path the 32
  actually governed was the chat being **had**, whose header `turnState.submit` writes from the
  local derivation and never revisits. Measured in Chromium, a 42-character first message read in
  full in that chat's own switcher row and cut at 33 characters in the header directly above it,
  both on screen at once, in a header box that fits 42 and so was not short of room. The overlay
  is now 48, the pair is the registry's third entry and the first in TypeScript, and the gate was
  proved to fail on a divergence before being trusted (ADR-0021 truncation addendum, 2026-08-03).
  **What is left of this entry:** a comparator field for the ordered relations, the copies that
  are not declarations, and the TypeScript-into-CSS names whose far side is a use. **Trigger:**
  the first coupling that actually drifts.

  **Landed 2026-08-08, four of the five kinds, and one of them turned out to be three**
  ([ADR-0029](../adr/ADR-0029-vision-screen-capture.md), the 2026-08-08 registry addendum). The
  registry moved to `scripts/couplings.py` and went from 3 entries to 14, behind two additions to
  the scan. **The comparator field** is `Relation.ORDERED`, holding an entry's sites to
  non-decreasing order in registry order, and two of the three orderings this entry named are
  registered: `MAX_EDGE_CEILING` at or below `MAX_IMAGE_EDGE`, and `MAX_CAPTURE_BYTES` at or below
  `MAX_RECEIVE_BYTES`, stated against the body's ceiling rather than the brain's copy of it,
  because the tree that produces the bytes is the one the transport limit is really about.
  **The mention** is the other addition, and it answers three of the five kinds at once, which is
  the finding rather than the feature: a key spelled inside a shell string, a stylesheet reading a
  name back with `var(...)`, and a bare literal a component compares against are one problem, that
  there is no declaration on that side to parse. A mention is a file plus a template carrying
  `{value}`; the scan renders the agreed value into it and requires the result to appear. It is
  not circular, the template carrying the shape and the site the value, and it dissolves the work
  this entry thought was left in the `thinking` case: a bare literal never has to become a named
  constant, because the check reads the use rather than a declaration. So `thinking`, the
  healthcheck's fourth copy of the seam-token key, the four TypeScript-into-CSS names, the
  `--ease` curve, and `capture_screen` (which needed nothing but registering) are all tied now.
  **One suite invariant was relaxed deliberately** rather than quietly: the test that refused an
  entry confined to one top-level tree now demands more than one suffix, since the overlay and its
  stylesheet are one tree and two languages and are exactly the rename this scan is for. Two new
  invariants replace what that loses, both aimed at this widening rather than at the tree: the
  registry must exercise both relations and both kinds of place, because a comparator no entry
  uses is the same defect in a wider gate. **Landed ahead of the trigger**, which was the first
  coupling that actually drifts; nothing had drifted, and each capability was reddened on the real
  tree instead, once per capability. **What this opens** is the entry below.
- **The four couplings the widened registry still cannot hold.** *Fix when it bites.* Opened
  2026-08-08 behind the landing above, in the same shape its own parent had: a registry that now
  reaches four kinds of coupling makes each remaining one a decision rather than an absence.
  A fourth joined the same day and is folded in here rather than counted again, since it is the
  same absence and a near-duplicate name would inflate the area. **Still four on 2026-08-09, by
  exchange rather than by standing still:** the duration below closed, and the shape that closing
  it left behind is written directly under it, folded in for the same reason the fourth was.
  **A membership, not an ordering.** `CAPTURE_MIME` (`"image/png"`) must stay inside the brain's
  `ALLOWED_MIME_TYPES`, which is a `frozenset` literal, so this wants a collection value form as
  well as a comparator, and the reducer refuses what it cannot reduce by policy rather than by
  omission. **Trigger:** a second capture encoding, which is the only thing that makes the set
  larger than one useful element.
  **A port with no declaration to read.** The body's bind port 50151 is a bare literal argument in
  `body/app/src-tauri/src/body_server.rs`, against `docker-compose.body.yml`'s
  `host.docker.internal:50151`. The brain's port was closable because its far sides are mentions
  and its near side became `DEFAULT_SEAM_PORT` in gated code; this one is the reverse, since the
  only place that could declare it is inside the one crate no gate compiles (the Tauri shell
  clippy entry above is that same hole). Landing a constant there to give the scan something to
  read means shipping a source edit nothing type-checks, which is a worse trade than leaving one
  port untied. **Trigger:** the shell entering CI, which that sibling entry already tracks.
  **A duration restated in another unit.** `overlay.css` spells the roll's length as `0.3s` at
  some thirty inline sites while `MORPH_ROLL_MS` counts milliseconds, so no template renders one
  into the other; the curve half of the same pair closed, `--ease` restating `EASING` verbatim.
  Closing it wants either a unit-aware value form with a per-site unit, which is a design rather
  than a field, or the overlay adopting a `--roll: 300ms` custom property every transition spends,
  which is a stylesheet change and belongs with the stylesheet's own entry above. **Trigger:**
  either of those two, or the first frame that shows a CSS transition and the roll beside it on
  two clocks.
  **Struck 2026-08-09**, by the second of the two ways it named, and with its own arithmetic
  corrected first. The sheet spelled `0.3s` **seven** times and not thirty: six declarations and
  one sentence about them, beside seven `300ms` that were every one of them prose in a comment, so
  the number was never restated in the constant's own unit anywhere. Thirty inline sites made this
  read like a sweep when it is two lines, which is the stale-account failure the index warns about.
  `:root` now carries `--roll: 300ms` and the two rules that move WITH a roll spend it: the section
  share caps' `max-height`, and the thoughts marker's turn. Both already said in their own comments
  that the roll's clock was theirs, which is what made them identifiable as the roll rather than as
  a duration that matches it. The other four declarations keep their literal on purpose, being the
  panel's summon fade (paired with its own 0.44s spring, accompanying no roll) and the three
  arrivals (`bubblein` on a bubble, `confirmin` on a chip and on a reminder row, each played on
  something that has just appeared): tying them would mean a retune of the roll silently retunes
  three features it has nothing to do with, which is the false tie this registry must not claim.
  **The unit-aware value form turned out to be unnecessary rather than deferred**, which is the
  finding: once the sheet spells the duration once, it spells it in the constant's own unit, and
  the mention is `--roll: {value}ms;` against `MORPH_ROLL_MS` with nothing new in the scan. Every
  rendered duration measured unchanged in headless Chromium at both `prefers-reduced-motion`
  settings, and the gate was reddened on a drift in each direction before it was trusted
  ([ADR-0029 addendum](../adr/ADR-0029-vision-screen-capture.md) of that date).
  **A custom property's spend, where the TypeScript declares the value and not the name.** Opened
  2026-08-09 by the close above, and folded in here rather than counted beside it for the reason
  the gRPC pair was. A mention renders a value, so it reaches `--roll: 300ms` on `:root` and cannot
  reach the two `var(--roll)` that spend it; the same is true of `--ease`, which has shipped that
  way since the registry widened. Where the TypeScript declares the NAME instead
  (`CEILING_PROPERTY`, `CHAT_FLOOR_PROPERTY`, `TRACE_ROW_PROPERTY`) the mention pins the spend
  exactly, so the gap is not the mechanism but which half of the pair the constant happens to be.
  What stands in for the gate today is the browser: a `var()` that resolves to nothing is invalid
  at computed-value time and takes the whole declaration with it, so a mistyped spend loses the
  transition outright rather than shifting it, which is visible in one look and was measured.
  Closing it wants either a name constant in `overlay/morph.ts` that nothing imports, which is a
  declaration existing only to be read by a gate, or a mention form that pins a rendered NAME
  rather than a rendered value. **Trigger:** a third property in this shape, or the first spend
  that is found mistyped.
  **A gRPC status code, spelled once per language's own casing.** Added 2026-08-08 with the
  gateway's kinded error currency ([ADR-0023](../adr/ADR-0023-body-gateway-volume.md)'s addendum
  of that date). The body writes `Status::resource_exhausted` and `Status::failed_precondition`;
  the brain's classifier keys on `grpc.StatusCode.RESOURCE_EXHAUSTED` and
  `FAILED_PRECONDITION`, and the two sides must agree or a refused capture is worded as a fault.
  Neither side declares a value the other could read: tonic's spelling is a method name and
  grpc-python's is an enum member, so a mention template would have to case-fold across the
  languages, which the reducer cannot do and should not learn for one coupling. What holds the
  pair today is prose in both module docs plus a test table on each side, which is exactly what
  the registry exists to replace. **Trigger:** a third caller of the same table, or a case-aware
  mention form arriving for another reason.

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
- **The `cortex_core/__init__.py` barrel is at its 300-line cap again, opened 2026-08-06 by the
  ranked-`select` widening ([ADR-0038](../adr/ADR-0038-ranked-recall.md)).** The 2026-07-14 entry in
  [tools-mcp.md](tools-mcp.md) bought the barrel its headroom back by halving the cost of a name
  from two lines to one (the redundant-alias re-export form, dropping `__all__`). That economy is
  spent: the surface is now ~290 names and the file sits at exactly 300 again, which this change got
  under only by trimming the module docstring. So the *next* public core name breaks the line cap
  for whatever unrelated slice adds it, exactly as before, and there is no second halving available.
  The options are all genuine changes of convention rather than economies, which is why this is
  recorded rather than done in passing: a sub-barrel per area with `cortex_core` re-exporting it
  (still one line per name, so it only moves the problem unless consumers import from the
  sub-barrel); the test doubles (`fakes*`) leaving the top barrel, which is a real responsibility
  split and is already how a few call sites import them, at the cost of touching many test files;
  or the barrel becoming an explicit `__all__` over star imports, which ruff bans as F403. **Fix
  when it bites**, which will be the next slice that adds a public core name.
  **It bit on 2026-08-06**, the same day, when the summarizing history window added four public
  core names (`SummarizingHistoryWindow`, `HistoryRecap`, `RECAP_MAX`, and the widened
  `HistoryWindow`). The sub-barrel option was taken, in the only form the record says actually
  works: the names live in their defining modules (`cortex_core.summarizing`,
  `cortex_core.sessions`, `cortex_core.windowing`) and **every consumer imports from there**, so
  the top barrel did not grow by a line and still sits at 300. Three call sites do it
  (`cortex_session.store`, the orchestrator's `window_builders`, the tests), each with a comment
  naming this entry, joining the one production precedent that already existed
  (`cortex_inference.backend` importing `cortex_core.inference`). What this does NOT do is decide
  the convention: the barrel is still full, the next name still has to choose, and a
  module-by-module escape leaves the tree with two import styles for core names until something
  settles which is normal. **Still fix when it bites**, and the fix is now a decision about the
  barrel's future rather than a hunt for headroom.

  **Landed 2026-08-06, the same night, as the third option in the form its objection missed
  ([ADR-0026 barrel addendum](../adr/ADR-0026-prose-style-gates.md)).** The decision this entry
  said was owed was taken rather than deferred again, and the criterion was the one the two
  bruises had established: whichever option left call sites alone. That ruled out the first two.
  A sub-barrel per area only relocates the wall unless consumers import from the sub-barrel, and
  the test doubles leaving the barrel is a real responsibility split whose bill is 155 files
  (measured, `from cortex_core import` across the brain workspace), spent entirely on import
  lines. The third option, `__all__` over star imports, is the only one that moves nothing, and
  the entry had recorded it as blocked by ruff's F403. It is not: `cortex_core/_surface/` now
  holds eight area modules (`ports`, `turn`, `tools`, `subagents`, `memory`, `schedule`,
  `residency`, `fakes`), each importing its area's names from their defining modules and
  declaring them in its own `__all__`, and `cortex_core/__init__.py` re-exports all eight
  wholesale behind one `per-file-ignores` line naming the file and the reason. Pyright had the
  second objection, `reportWildcardImportFromLibrary`, which fires because the package resolves
  through its own editable install and which a relative import inside the source tree does not
  trip, so the barrel is the one relatively-importing file in the brain and needs no suppression.
  **The numbers:** 300 lines to 18, 290 public names to 294, and the largest sub-barrel at 151.
  `PLAIN_SECURITY_PREAMBLE` is back on the public surface with `HistoryRecap`, `RECAP_MAX` and
  `SummarizingHistoryWindow`, which is the whole of the inconsistency the two bruised slices left;
  the two production call sites that had imported them from their defining modules with a comment
  citing this entry now import them from the barrel like everything else, so the tree is back to
  one import style. **Honest about the headroom:** it is not unlimited, it is per area, and the
  areas are uneven. `ports` at 151 lines has room for about 130 more names and `subagents` at 34
  has room for about 250, but a name lands in the area it belongs to rather than the area with
  space, so a run of port additions is the case that reaches a cap first. What is different is
  that reaching it costs an ordinary split by responsibility inside one area rather than a third
  round of this argument, and that the gate was never touched to get here.
- **A compose bind default that lands in the repo tree is stageable, and nothing but `.gitignore`
  says otherwise.** *Fix when it bites.* Opened 2026-08-06, when `models/` was found root-owned and
  empty at the repo root, created that morning by a container and matched by no ignore rule;
  `pgdata/`, where the pg-backup sidecar writes `cortex.dump` (`CORTEX_DB_DIR`,
  [runbooks/memory-pgvector.md](../runbooks/memory-pgvector.md)), carried the same exposure and had
  carried it since that sidecar shipped. Both are ignored now, unanchored so they match at any
  depth, because compose resolves a relative bind against the **project directory**: the `just`
  recipes pass `--project-directory .` and a bare `docker compose -f
  docker/docker-compose.memory.yml` does not, which puts the same two under `docker/` instead. A
  third default of the same shape, `${CORTEX_TOOLS_ROOT:-./sandbox}`, was already ignored, and that
  is the point rather than a reassurance: the tree is clean by three separate acts of remembering
  and not by anything that checks. What is deferred is the check. Six bind defaults exist today
  (four spell `${CORTEX_MODELS_DIR:-./models}`, one `${CORTEX_DB_DIR:-./pgdata}`, one the sandbox),
  every one of them written by root from inside a container, and the artifacts are GGUFs and
  database dumps rather than kilobytes, so what this class fails as is a multi-gigabyte blob one
  `git add -A` from the index. The fix is a scan reading the `${VAR:-./path}` defaults out of
  `docker/*.yml` and failing when one is not matched by `.gitignore`, which is `crosscheck.py`'s own
  trick of tying two files that must agree and is the size of it too. The trigger is the next
  override that adds a bind default, since a scan written today would guard a set of three that is
  already correct.

  **Landed 2026-08-08, ahead of its trigger, and the entry's own sketch of the fix was wrong in
  two ways worth recording.** `scripts/bindcheck.py` is a fourth cross-tree scan beside the line
  cap, the dash ban and the constant registry, run unconditionally by `just check` and by CI
  ([ADR-0026 bind addendum](../adr/ADR-0026-prose-style-gates.md)). The six defaults across five
  files reproduced exactly as written above. What did not survive contact was the rule: this entry
  proposed "failing when one is not matched by `.gitignore`", and that rule is false about the
  tree it would have gated. Three more binds in `docker-compose.memory.yml` point at
  `./docker/postgres/init.sql`, `live-contract-db.sql` and `backup.sh`, which are inputs the repo
  ships and must never be ignored, so the honest rule is a three-way one: a bind source resolves
  **outside** the repo, or onto a path git **tracks**, or onto a path git **ignores**. The second
  way it was wrong is narrower and matters more for the trigger: reading only `${VAR:-./path}`
  would walk straight past a plain `source: ./cache` added later, which is exactly the "next
  override" this entry was waiting for. The scan reads bind mounts, not variable syntax, and finds
  compose files by name anywhere under the root rather than by a `docker/*.yml` glob.
  **Two things the writing turned up.** Compose materializes a **directory**, and a directory-only
  ignore pattern (`models/`) does not match a path git cannot stat, so `check-ignore` has to be
  asked with a trailing slash or the gate reports every one of these bare; that was found by the
  scan flagging all six on its first run, which was the scan being wrong rather than the tree. And
  the unanchored-on-purpose note in `.gitignore` is now enforced rather than remembered: the scan
  resolves every relative source against both project directories compose can pick, so an anchored
  `/models/` is reported for leaving `docker/models` uncovered.
  **No pre-existing violation was found.** The tree was clean on the first correct run, which the
  entry predicted ("a scan written today would guard a set of three that is already correct"), and
  the value is entirely in the fourth case. It was therefore reddened deliberately before being
  trusted: a planted `docker/docker-compose.cache.yml` carrying `${CORTEX_CACHE_DIR:-./hfcache}`
  drew two complaints and exit 1, and deleting the `models/` line from `.gitignore` drew eight
  across four overrides; both returned to `bindcheck OK` on revert. The reader is
  `scripts/composemounts.py`, split out because the two together are over the line cap, and it
  raises rather than skips on every compose shape it was not taught, since a reader that quietly
  walked past a new override's one mount is the same gate-that-cannot-fail in a different place.

- **A mention counts nothing: one occurrence satisfies it, however many the file spends.**
  *Fix when it bites.* Opened 2026-08-08 when the mention matcher was bounded. A `Mention` asks
  whether a file spells the agreed value in the template's shape, and one bounded occurrence is
  enough, so a file spending it twice can lose one of them with the gate green. That is not
  hypothetical: `Message.tsx` compares against `"thinking"` on two adjacent lines and `overlay.css`
  reads `[data-morphing` in three rules, and an ADR published a mutation proof that assumed
  otherwise (corrected where it was published). What was chosen instead of a count is the word
  boundary, because a count ties a registry entry to how many times a stylesheet happens to spend
  a custom property, and every legitimate new rule would then redden a gate about a coupling that
  never moved. The fix, if it bites, is a per mention `occurrences` field carrying an exact count
  where one is meaningful and staying unset where it is not, which is a field rather than a design,
  since `check_mention` already renders one needle and would only count matches instead of
  searching for the first. **Trigger:** a mention whose several occurrences are genuinely a set
  that must move together, the first being a state literal compared in two components rather than
  one, at which point the count is carrying real information and not just arithmetic about a
  stylesheet.

  **Landed 2026-08-09, on the trigger, and the entry was right that it is a field rather than a
  design.** `Mention.occurrences` is optional; `check_mention` counts bounded matches instead of
  stopping at the first, and reports found against pinned
  ([ADR-0029 counted-mentions addendum](../adr/ADR-0029-vision-screen-capture.md)). Both live
  cases reproduced exactly as this entry describes them, counted against the tree rather than
  taken on its word: `Message.tsx` spells `message.statusState === "thinking"` twice and
  `overlay.css` reads `[data-morphing` in three rules, and each of the other eleven mentions the
  registry carried that morning occurs exactly once.
  **The comparison is exactly N rather than at least N**, which is the decision this entry left
  open. A floor passes on a far side that grew past it, and having passed once it also passes when
  that far side drops back, so the gate widens by however much the tree drifted with nothing
  saying when; an exact count is falsifiable both ways and costs one integer in `couplings.py`
  when an addition is deliberate. The disable risk the entry worried about is answered by the
  field being opt in rather than by weakening the comparison.
  **The stylesheet objection survived and shaped what got registered.** `Message.tsx` is pinned
  at 2, its two comparisons being the `className` and the `aria-label` of one chip. The three
  `[data-morphing` rules are **not** pinned at 3, because three is the sum of two unrelated
  features (a scrollbar thumb hidden mid-roll, and two section share caps), which is exactly the
  arithmetic this entry declined; the two share caps alone are a set, so they carry a narrower
  mention of their own, `:not([{value}="0"])` at 2, with the bare presence check left standing
  over all three. Everything spent once stays unpinned.
  **Proven able to fail in both directions, on the real tree.** The rename applied everywhere but
  `Message.tsx`'s second line exits 1 naming 1 against 2, and the same mutation under the scan as
  it stood the day before exits 0, which is this entry's defect measured rather than asserted; a
  third comparison added exits 1 naming 3 against 2; one of the two share-cap rules stripped exits
  1 naming 1 against 2; and a fourth rule reading the attribute in an unpinned shape stays green,
  which is the benign growth the design has to tolerate. Every perturbation was reverted and the
  scan returned to `crosscheck OK` after each.
  **No new deferral is opened, and that is a decision rather than an omission.** Two limits remain
  and are written into the ADR beside the behaviour: a count is over one file, so there is no way
  to say "six across three files", and it is over one rendered needle, so the same value spent in
  another shape is invisible to it. Neither has a case in the tree, every other coupling being
  single-file and single-shape, so filing either would inflate the backlog with a capability
  nothing is waiting on; the entry above on the couplings the registry still cannot hold is where
  a real one would join.
  **One bookkeeping repair rides along.** This entry was appended on 2026-08-08 without being
  added to the open list above or to the count in [index.md](index.md), both of which read 6 while
  seven were open and named the same six. Closing it makes the number true rather than moving it,
  and the six named there are unchanged.
