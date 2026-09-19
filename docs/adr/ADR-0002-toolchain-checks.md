# ADR-0002: Toolchain and check mechanics

**Status:** Accepted (2026-09-19)

## Context

AGENTS.md sets the required checks and the one `just check` that CI and pre-commit both run.
Turning them into running machinery left open which Rust toolchain can measure branch coverage,
how a threshold cargo-llvm-cov cannot express is enforced, where tests and generated code sit
relative to the 300-line limit, and how the lint policy is configured.

Running the checks raised four more questions. The coverage step runs on a nightly channel that
moves on its own, and once failed with a log that did not say why. The live contract suites ran
against the stores holding the brain's real state, so they reported on that state instead of on
the adapter. Every suite ran in collection order, so a test depending on what a sibling left
behind could pass indefinitely. And a mutation table, the proof that a check can fail, was never
re-run by anyone but its author.

## Decision

### Toolchains and lint policy

1. **Rust branch coverage runs on nightly; everything else on stable.** LLVM branch instrumentation
   (`cargo llvm-cov --branch`) is nightly-only, so only the coverage step invokes
   `cargo +nightly llvm-cov`. CI installs nightly before stable, so stable stays the default.
2. **The Rust coverage threshold is enforced by `scripts/coverage_gate.py`.** cargo-llvm-cov has no
   `--fail-under-branches`, so the step exports JSON (`--json --summary-only`) and the script
   requires exactly one `data[]` entry and `covered == count` for each of
   `data[0].totals.{lines,regions,branches}`. The producer's `percent` is never read; a printed
   percentage is recomputed from the counts. A metric whose count is 0 passes with a printed note.
3. **`scripts/` is a standalone uv project (`repo-checks`), not a brain workspace member.** Repo
   tooling is not brain domain code and it scans every tree. It is checked like all other Python.
4. **Generated code lives in directories named `_generated`.** The line-limit scan skips any path
   with a `_generated` component and every coverage configuration excludes the same (ADR-0001
   decision 7). The scan also skips build output, `dist` and `coverage` (ADR-0011).
5. **Tests live outside counted source files.** The line-limit scan excludes `tests/` directories
   plus `test_*.py`, `*_test.py`, `conftest.py`, `*_test.rs`, and the overlay's `*.test.ts`,
   `*.test.tsx` and `test-setup.ts` (ADR-0011). An inline `#[cfg(test)]` module is permitted only
   to unit-test private internals the public API cannot reach, as in
   `body/crates/rpc/src/status.rs`, and it counts toward the file's limit.
6. **Ruff runs with `select = ["ALL"]`** and a short, individually justified ignore list in the
   root `ruff.toml`, shared by every Python project in the repo.
7. **Rust policy:** edition 2024; `unsafe_code = "forbid"` and clippy `unwrap_used` and
   `expect_used` denied through workspace lints, relaxed in tests by `clippy.toml`; clippy pedantic
   at warn, which `-D warnings` escalates. An OS adapter crate that needs `unsafe` gets its own ADR
   and a scoped lint override, per AGENTS.md rule 5.
8. **Python policy:** CPython 3.12 baseline; pyright strict; the `integration` pytest marker is
   deselected in `addopts` (`-m "not integration"`), so live suites stay out of the coverage
   threshold.
9. **The pre-commit stage is one local hook running `just check`**, a literal mirror, so the hook
   cannot diverge from the command. The commit-msg stage runs the two message checks AGENTS.md
   describes.

### Rust coverage on an unpinned nightly

10. **The coverage run excludes Cargo build scripts** (`--ignore-filename-regex
    '/_generated/|/build[.]rs$'`). Newer nightlies instrument them
    ([reading](../readings/rust-coverage-toolchain.md)), and a build script runs under cargo at
    build time, outside any test binary, so no test can reach it. The dot is a character class
    because the pattern passes through a just recipe line before llvm-cov reads it.
11. **The toolchain stays a channel, and the step prints what it measures with.** `check-body` runs
    `rustc +nightly --version` and `cargo +nightly llvm-cov --version` on every run, before the
    measurement. CI runs the same recipe, so both sides print them, and a machine with no nightly
    fails at a probe that names it. When an upstream change causes a failure, those two lines tell
    it apart from the commit under test.
12. **`coverage_gate.py` alone decides the coverage result.** The measurement is run with no
    `--fail-under-*` flag: with the report diverted to a file those flags exit 1 without naming a
    metric or a threshold ([reading](../readings/rust-coverage-toolchain.md)), which pre-empted the
    check that does name them. The script prints one PASS or FAIL line per metric in every case.
13. **The result names the toolchain that produced it.** The export records its writer in
    `cargo_llvm_cov.version` beside the llvm export format's `version`, and an export without both
    is refused. The recipe passes its probes as `--rustc` and `--llvm-cov`, both required, so a
    recipe edit that drops one is a usage error (exit 2) rather than a silent pass; a default would
    have to be an expected version, which is a version lock again. `--llvm-cov` must match the
    export's own record, or the numbers judged are not the ones this run measured; the compiler is
    not in the export, so `--rustc` is only printed. Two command substitutions on one recipe line
    fill both, in one shell, so a toolchain that empties one empties the other and the empty
    `--llvm-cov` fails visibly; the `check-body` comment records this, since filling either value
    from elsewhere would let an empty `--rustc` pass alone.

### Live contract runs use their own store

The `integration` suites drive real stores, on a developer machine the ones holding the brain's
state. Real sessions newer than a fixture's dates failed a correct adapter through
`list_sessions(limit=3)`, one real memory failed `check_empty_search`, and two suites skipped
whenever real records existed, passing while asserting nothing.

14. **The live Redis runs select logical database 15.** `brain/packages/session/tests/live_redis.py`
    rewrites the configured URL's path onto `LIVE_DB`, and `reset` empties that database before the
    suite and after every check. Every check starts from the empty store the fakeredis fixture
    gives it, so the fake and the real adapter run the same suite, with no skips and no deletes by
    key prefix. Production still selects database 0, with no new setting. `live_redis_url` refuses
    a `CORTEX_REDIS_URL` that already selects `LIVE_DB` or names no database in its path, and
    `reset` re-reads the database its client opened and refuses to flush any other.
15. **The live pgvector run opens its own database, `cortex_contract`.**
    `brain/packages/memory/tests/live_postgres.py` rewrites the database name in the
    `CORTEX_MEMORY_DSN` path, and `reset` runs `TRUNCATE TABLE memories` before the run and after
    every check. `docker/postgres/live-contract-db.sql` is a second initdb script that creates the
    database and includes `init.sql`, so both databases are built from one definition. On a data
    dir that predates it the run fails before any check (`InvalidCatalogNameError`, or
    `to_regclass('memories')` returning null) and prints the two statements that create it, instead
    of falling back to the configured DSN. The same protections as decision 14 apply, with `reset`
    checking `current_database()`. The `pg-backup` sidecar dumps `-d cortex`, which leaves this one
    out.

### Test order

16. **Every checked suite runs in a shuffled order under a fixed seed.** `pytest-randomly` is a dev
    dependency of both Python projects, with `--randomly-seed` in each `addopts` (`9973` for
    `brain/`, `7919` for `scripts/`), and `body/app/vite.config.ts` sets
    `sequence: { shuffle: true, seed: 65537 }`, so `just check` runs every suite out of collection
    order and in the same order twice. A fixed seed still finds new dependencies, because
    `pytest-randomly` draws a position per test: a new test's position is drawn when it is added,
    and existing tests keep their relative order
    ([reading](../readings/test-order-shuffle.md)). Its per-test reseeding of `random` affects
    nothing: the one random draw in checked Python, `contrast.py`'s resampler, uses its own
    `random.Random(seed)`. The seeds are arbitrary and frozen, since changing one discards every
    order the suite has passed; they differ deliberately, and no `crosscheck.py` entry ties them.
17. **The Rust suite is shuffled on the nightly coverage step, at seed `104729`.** libtest accepts
    `--shuffle-seed` only on nightly after `-Z unstable-options`, and decision 1 keeps `cargo test`
    on stable. The coverage step already runs the whole workspace on nightly, so it takes the flag
    at no extra wall time, and `just check` runs the Rust suite twice, alphabetically on stable and
    permuted on nightly. The seed is in the `justfile` because libtest reads it only from the
    command line. libtest seeds its order with the seed and a hash of the binary's test names, so
    adding a test redraws that binary's whole order ([reading](../readings/test-order-shuffle.md)).
    Each binary prints `(shuffle seed: 104729)` in its header.
18. **`just shuffle [seed]` runs the orders the fixed seeds never produce, weekly, in a workflow
    that blocks nothing.** The recipe runs all four suites at one seed, drawn and printed when none
    is given; its Rust step is a plain `cargo +nightly test`. `.github/workflows/shuffle.yml` runs
    it every Monday (`41 3 * * 1`) and on `workflow_dispatch` with an optional seed. The job draws
    the seed itself, refuses anything but digits, passes the dispatch input through the
    environment, and writes the seed and `just shuffle <seed>` to the run summary before the run
    starts, so a failed or cancelled run still names its order. It blocks nothing, so a failure
    arrives detached from any commit, which is accurate since the pair of tests it finds already
    coexisted. It runs the committed recipe whole, with no CI-only variant (ADR-0006).

### Mutation tables and the replay pass

19. **A mutation table is written, fenced, in the body of the commit that makes it, and names the
    file, the edit and the suite its counts are over.** The table lists the edits that make the
    suite fail and how many cases each one takes down; the tree that produced those counts is gone
    once the change is committed, so the table is its author's report until somebody replays it.
    The replay pass reads commit bodies, and the fence exempts the columns from the width rule. The
    diff shows the file and the edit but not the suite, and a count replayed over another
    collection differs. AGENTS.md states both; no machine checks them.
20. **A replay pass is due once 25 candidate bodies have been committed since the last pass, and it
    replays five drawn blind from the 25 most recent.** A candidate body is a commit message
    matching the `replay` recipe's vocabulary. The cadence counts bodies, not tables, because
    commits arrive in bursts and neither a message nor its diff says reliably which bodies contain
    a table; 25 bodies held 15 tables when measured, so a pass replays about one table in three
    ([reading](../readings/mutation-replay.md)). Five tables took the first pass about an hour, and
    25 bodies is about one overnight session's output. `just replay` keys each candidate on a
    digest of the seed and its commit hash and takes the smallest keys, so nobody picks the tables
    they already understand; a recorded seed therefore reproduces its draw only on the checkout it
    drew at, which the recipe prints beside the seed. A late pass is given the last pass's date and
    draws over the whole gap.
21. **A drawn body with no table of its own is replaced by the next body in the same seed's
    order**, until five have a table or the window runs out. A body has no table when its own
    commit measured none; one pointing at another commit's table is passed over, and that table may
    be replayed beside the sample. A table whose wording defeats reconstruction stays in the sample
    and is recorded as unreplayable, since passing over the hard tables would be a hand-picked
    choice. Reading each body decides which have tables, so the first five of the rest are still a
    uniform draw.
22. **The recipe states whether a pass is due, counted from the ledger.** With no date it prints
    the last pass, the candidate bodies since it, the cadence and the result. The count is the
    range `<commit>..HEAD` from the ledger's "Drawn from" column, anchored on the resolvable commit
    nearest HEAD whatever the row order; that column holds the commit the draw ran at, since a
    pass's own commit does not exist when its row is written. Only when no row's commit resolves
    does the count run from midnight of the last dated row, and the line says which of the two it
    used. The cadence is the `window` parameter used in both roles, so the two cannot disagree.
23. **A row that does not reproduce is first treated as a suspect replay**, re-run from a clean
    state, since stale `__pycache__` and a partial edit have both produced false counts here. Then
    a wrong count goes in the pass's ledger row, since a committed body is not edited; a count of
    zero is a defect answered with a new assertion, unless only a live run reaches the line; a
    wording the body and diff do not identify is recorded unreplayable after about five minutes,
    since a guessed edit can produce a false correction; a row whose tree has moved on is expired.
24. **The procedure and a ledger of passes live in
    [docs/runbooks/mutation-replay.md](../runbooks/mutation-replay.md)**, one row per pass even
    when nothing is found, because the next count runs from it. A person or an agent runs a pass,
    not a workflow: rebuilding an edit from a sentence needs judgement no runner has.

## Consequences

- Every machine that runs `just check` needs nightly with `llvm-tools-preview` and cargo-llvm-cov,
  neither of them version-locked. An upstream nightly change can cause a failure with no change
  here, on whichever run comes next; the printed versions diagnose it. The coverage script depends
  loosely on the export format, and a format change fails visibly with typed errors.
- `select = ["ALL"]` means a new ruff release can introduce failures; fixing or narrowly ignoring
  them, with a reason, is routine maintenance.
- Logical databases do not exist on Redis Cluster; this stack is one loopback-only container
  (ADR-0001). A schema change to `init.sql` has two databases to reach on an existing data dir
  ([memory-pgvector runbook](../runbooks/memory-pgvector.md)). Live tests at the gRPC boundary
  share the running brain's stores and assert relative properties, which is what makes sharing
  safe.
- A planted order dependency fails at a given seed about half the time, so the fixed seeds catch
  about half of new dependencies when they are added and the weekly run finds the rest
  ([reading](../readings/test-order-shuffle.md)). A Rust failure can name a pair its commit did not
  touch, and since libtest runs tests in parallel threads, shuffling two tests inside one thread
  window changes nothing that was not already a race.
- `-p no:randomly` exits 2, leaving the `--randomly-seed` in `addopts` unrecognized. The plugin is
  in the `dev` group, so the brain image (`--no-dev`) lacks it, and coverage totals do not move.
- The weekly workflow has never run, because Actions is off for this repository, and nothing in the
  tree records a run's seed or result
  ([R-291](../refinements/tasks/291-a-red-sweep-leaves-no-trace-in-the-repo.md)).
- The replay sample size and window are written in the recipe, its comment, the runbook and here,
  and `crosscheck.py` has no reader for a justfile or a number written as words
  ([R-440](../refinements/tasks/440-the-replay-sample-is-spelled-in-three-places.md)).
- A rewrite of history moves recorded commits: a recorded seed stops reproducing its draw, and the
  count anchors on an older row that still resolves or falls back to the date
  ([R-667](../refinements/tasks/667-a-dateless-row-is-passed-over-by-the-commit-anchor.md)).

## Alternatives rejected

- **A dated nightly version lock.** Nightly runs about two releases ahead of stable, so within a
  few months a locked version falls behind the stable the rest of the checks use, and a newly
  stabilized feature then fails only under coverage. Locking the compiler alone leaves
  cargo-llvm-cov free, and that tool reads the compiler's LLVM output, so it has to move with it.
- **Comparing toolchains across sides, or recording the last green compiler.** Both need an
  expected version written down, which is a version lock; a committed record fails this machine
  once CI writes a newer date, and an ignored one is absent on a fresh CI checkout. Reading the
  compiler from cargo's `.rustc_info.json` ties the check to an undocumented cache layout.
- **Requiring non-empty `--rustc` and `--llvm-cov` values.** The only caller cannot produce an
  empty `--rustc` alone, which holds only while both values come from one shell
  ([R-335](../refinements/tasks/335-the-relays-share-one-shell.md)).
- **A key prefix or namespace on the stores.** A production setting whose only caller is a test,
  which splits the brain's state silently when misconfigured. Future-dated fixtures went with it.
- **A Postgres schema plus `search_path`.** The adapter's SQL is unqualified, so a `search_path`
  that fails to apply sends every query, the `TRUNCATE` included, to the brain's own table without
  an error. Creating the contract database from the test was also rejected: a test would provision
  databases against whatever DSN it is given.
- **A per-run random seed in `just check`, a daily cached seed, or rotating the fixed seed.** Each
  one puts an order nobody chose where a failure blocks a commit. A `schedule:` trigger on `ci.yml`
  runs all three toolchains, since its `changes` job has no diff to classify.
- **`cargo-nextest` as a second test runner.** libtest's own shuffle needs none.
- **A `commitlint.py` rule requiring a body with a mutation table to name a tracked path.** Most
  bodies matching the vocabulary name none ([reading](../readings/mutation-replay.md)), so it would
  fail accurate messages, and any path would satisfy it
  ([R-359](../refinements/tasks/359-the-table-detector-is-refused-not-impossible.md)).
- **A wider replay window.** The older a table, the likelier the tree under it has moved on.

## Related

- Modules: [repo checks](../modules/repo-checks.md), [brain-session](../modules/brain-session.md),
  [brain-memory](../modules/brain-memory.md), [body-core](../modules/body-core.md).
- Runbooks: [local-dev-wsl](../runbooks/local-dev-wsl.md) (toolchains, a shuffled failure, the live
  runs), [mutation-replay](../runbooks/mutation-replay.md) (the procedure and the ledger).
- Readings: [rust-coverage-toolchain](../readings/rust-coverage-toolchain.md),
  [test-order-shuffle](../readings/test-order-shuffle.md), [replay](../readings/mutation-replay.md).
- ADRs: [ADR-0001](ADR-0001-architecture.md), [ADR-0006](ADR-0006-check-performance.md),
  [ADR-0011](ADR-0011-body-v1.md).
