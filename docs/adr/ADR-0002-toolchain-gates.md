# ADR-0002: Toolchain and gate mechanics (Slice 1)

- **Status:** Accepted
- **Date:** 2026-06-28

## Context

Slice 1 turns AGENTS.md's hard gates into running machinery. Wiring them exposed
decisions the spec left open; this ADR records them so no future agent re-derives them.

## Decisions

1. **Rust branch coverage runs on nightly; everything else on stable.** LLVM branch
   instrumentation (`cargo llvm-cov --branch`) is nightly-only. All build/lint/test
   gates stay on stable; only the coverage step invokes `cargo +nightly llvm-cov`.
   In CI, nightly is installed before stable so stable remains the default toolchain.
2. **The Rust branch threshold is enforced by `scripts/coverage_gate.py`.**
   cargo-llvm-cov has `--fail-under-lines/-regions` but no `--fail-under-branches`, so
   the gate exports JSON (`--json --summary-only`) and the script requires exactly one
   `data[]` entry and `covered == count` for each of
   `data[0].totals.{lines,regions,branches}`. The producer's `percent` is never
   trusted (a metric with count 0 is vacuously satisfied, noted aloud).
3. **`scripts/` is a standalone uv project (`repo-gates`), not a brain workspace
   member.** Repo tooling is not brain domain code and must scan both trees; it is
   still gated exactly like all other Python (ruff, pyright strict, pytest at 100%).
4. **Generated-code marker: a directory named `_generated`.** The linecap scan skips
   any path containing a `_generated` component; coverage configs must exclude the same
   (implements ADR-0001 decision 7). No generated code exists yet; Slice 2 uses this.
5. **Tests live outside counted source files.** Rust tests go in `tests/` directories;
   Python tests in `tests/` directories. The linecap scan excludes `tests/` dir
   components plus `test_*.py`, `*_test.py`, `conftest.py`, `*_test.rs`.
   *Amended (2026-08-03):* the scan reaches the overlay's TypeScript too, so both lists
   grew, this one by Vitest's own `*.test.ts`/`*.test.tsx` plus `test-setup.ts`, and
   decision 4's by `dist` and `coverage`. The suffixes, the skips and what stays outside
   the cap are decided in the [ADR-0011](ADR-0011-body-v1.md) line-cap addendum.
   *Amended (Slice 2):* a narrowly-scoped inline `#[cfg(test)]` module is permitted
   when it unit-tests private internals unreachable through the public API (first use:
   the status-mapping helpers in `body/crates/rpc/src/client.rs`). Inline tests count
   toward the file's 300-line cap, which keeps them small; prefer `tests/` whenever
   the behavior is publicly reachable.
6. **Ruff runs with `select = ["ALL"]`** and a short, individually-justified ignore
   list in the root `ruff.toml`, shared by every Python project in the repo.
7. **Rust policy details:** edition 2024; `unsafe_code = "forbid"` and clippy
   `unwrap_used`/`expect_used = "deny"` via workspace lints (relaxed in tests through
   `clippy.toml`); clippy pedantic on at warn (escalated by `-D warnings`). A future OS
   adapter crate that genuinely needs `unsafe` gets its own ADR plus a scoped lint
   override, per AGENTS.md gate 5.
8. **Python policy details:** CPython 3.12 baseline; pyright strict; the `integration`
   pytest marker is excluded via addopts (`-m "not integration"`) so live suites never
   count toward or run under the coverage gate.
9. **pre-commit is a single local hook running `just check`** (a literal mirror), so
   the hook can never drift from the gate.

## Consequences

- A second toolchain (nightly) must be present for coverage runs; `rustup toolchain
  install nightly --component llvm-tools-preview` is part of machine setup.
- The coverage gate's JSON parsing couples loosely to cargo-llvm-cov's export format;
  the schema check fails loudly (typed errors) if the format shifts.
- `select = ["ALL"]` means new ruff releases can introduce new failures; fixing or
  narrowly ignoring them (with a reason) is part of routine maintenance.

## Addendum (2026-07-18): test-order randomization is not installed, so it is not a gate

A review of the brain-handoff work found several repair reports citing `-p no:randomly` on the
commands they ran, as evidence that ordering had been controlled for. It is not evidence of
anything here: `pytest-randomly` is **not** a dependency of the brain workspace (nor of
`scripts/`), so `-p no:randomly` disables a plugin that was never loaded and every suite has
always run in collection order. A flag naming an absent plugin reads exactly like a gate that
cannot fail, which is why this is written down rather than quietly dropped.

**What was done instead of citing it.** The plugin was supplied for the run only, with
`uv run --with pytest-randomly pytest -p randomly --randomly-seed=N`, and the suites were
actually shuffled: three seeds over `packages/core` (990 tests each) and one over the whole brain
workspace (1642 tests), all green, with `--collect-only` confirming the collected order really
differs between seeds, so the shuffle was doing something. That is the measurement the
determinism claim now rests on, and the chaos suite's own docstring says so.

**Why it is not being added to `just check`.** Making it standing would change what the gate
does on every run: the order becomes different each invocation, so a failure is reproducible only
by reading the seed out of the log, and the plugin also reseeds `random` per test, which is a
behaviour change for any test that draws. Both are defensible, but they are a gate-policy
decision with a real cost at personal scale, and the measured shuffles above found nothing for
them to catch. Recorded as a fix-when-it-bites deferral in
[docs/refinements/index.md#repo-gates](../refinements/index.md#repo-gates) with its trigger: a test that
passes alone and fails in a suite, or any order-dependent flake.

## Addendum (2026-08-03): a live contract run gets a Redis database of its own

Decision 8 above says the `integration` marker keeps live suites out of CI and out of the
coverage gate. It never said what store those suites run against, and the answer had silently
become "the one the brain keeps its real state in". A contract suite that the fake and the real
adapter both pass is this repo's port discipline in one artifact, so a live run of it that
reports on the store's contents rather than the adapter's behaviour is a broken signal, and all
three of the Redis-backed live suites had become one.

**What was found.** `uv run pytest -m integration --no-cov packages/session` failed in
`contract.check_a_pinned_chat_escapes_the_recency_window`. That check seeds one old chat plus
three newer ones, pins the old one, and reads `list_sessions(limit=3)`, so its three newer chats
have to BE the recency window for the pin to be the only reason the old chat appears. Its fixture
dates are fixed at 2026-07-03 (score 1783065600), while the compose Redis held sixteen real
sessions dated 2026-07-16 through 2026-07-21 (the newest, `audit-session-2`, at 1784660895). The
window was therefore filled by real chats, `mine_newer` came back empty, and the run blamed a
correct adapter. Reproduced on a clean worktree, so it predates the work that surfaced it.

**Why no sweep could have fixed it.** The suite already sweeps by the `contract-` prefix after
every check, which is what the ADR-0021 sweep addendum decided, and the sweep is scoped that way
precisely so real sessions are never touched. The crowding comes from those untouchable real
sessions, so the sweep is the wrong instrument by construction. That addendum saw the shape of it
and wrote the residual down against a `limit=50` window, meaning fifty more-recent real sessions
before it would bite. Two days later the pinning addendum landed a `limit=3` check on the same
assumption and lowered the trigger to three, without the recorded residual being revisited.

**The other two suites had answered the same hazard by going quiet.** The handoff suite skipped
whenever a real handoff was active, and the schedule suite skipped the moment a single real
schedule existed, both because their checks assert exact global views. A skip is the same broken
signal wearing the other mask: it reports green having asserted nothing, and it gets more likely
exactly as the machine gets more real state on it.

**Decision: the live runs select their own Redis logical database.** Redis serves sixteen
databases out of the box and this repo selects 0 everywhere in production (`DEFAULT_REDIS_URL`,
and the `CORTEX_REDIS_URL` docker/docker-compose.yml sets), so the live contract runs take
database 15. `brain/packages/session/tests/live_redis.py` owns the whole mechanism: it rewrites
the configured URL's path onto `LIVE_DB`, and its `reset` empties that database before the suite
and again after every check. Three consequences fall out. Every check now starts from the empty
store the fakeredis fixture already gave it, so the fake and the real adapter run the identical
suite instead of one suite and a hedged version of it. Both skips are gone, because there is
nothing real in that database to disturb. And the sweeps are gone with them, which removes a
coupling worth naming: each sweep restated the adapter's key layout inside the test
(`cortex:sessions`, `cortex:sessions:pinned`, the schedule suite's four index keys), a copy that
silently rots the day an adapter grows a key, and a whole-database flush needs to know none of it.

**Nothing about this reaches production configuration.** The adapters are untouched: their key
constants are unchanged and no store gained a prefix, a namespace, or a database argument.
`DEFAULT_REDIS_URL` still ends in `/0`, the compose file still sets `redis://redis:6379/0`, and
no new environment variable exists to be set wrongly. The database index lives in one test-only
module that production code never imports. Two guards make the flush safe by construction rather
than by argument: `live_redis_url` refuses a `CORTEX_REDIS_URL` that already selects `LIVE_DB`
(that would mean the brain is pointed at the database `reset` empties) and refuses a scheme that
does not carry the database in its path, and `reset` re-reads the database its client actually
opened and refuses to flush anything but `LIVE_DB`, so the check sits where the damage would be
rather than only where the URL was built.

**Alternatives rejected.** A key-prefix or namespace argument on the stores would isolate the run
too, but it puts a knob in production code whose only caller is a test, and a misconfigured one
splits the brain's state in two silently rather than failing; the store adapters are meant to
translate and hold nothing else. Re-deriving the check as a relative property was considered
hardest, since it is the option that changes no infrastructure, but the property under test is
about a bounded window, so observing it means controlling what is in that window; the only way to
do that without owning the store is to date the fixture chats into the future, which is a lie
that breaks the first time real data is future-dated, and it would have to be repeated in the
four other checks that read a `limit=50` window. Flushing the shared database is what the
prefix sweeps exist to avoid. Leaving the skips in place keeps two suites that assert nothing.

**Evidence (agent, Docker plus the real compose Redis, 2026-08-03).** With the sixteen real
sessions still present, `uv run pytest -m integration --no-cov packages/session` goes from one
failure to `3 passed`, and database 0 is byte-identical across the run (18 keys and 16 recency
members before and after) while database 15 is left empty. The check still has teeth: deleting
the pinned union from `RedisSessionStore.list_sessions` (`ids = recency_ids` alone) reddens
`assert old in ids` at `contract.py:207`, which is the assertion the pinning addendum said it
should. Both guards were fired rather than reasoned about: `CORTEX_REDIS_URL=redis://127.0.0.1:6379/15`
fails the run with `selects database 15, which the live contract runs reserve and empty`, and
calling `reset` on a client opened against database 0 fails with `refusing to flush Redis
database 0; the live runs own 15`, leaving all 18 keys in place.

**Known limits, and the deferral this opens.** Logical databases do not exist on Redis Cluster,
which serves database 0 only; this stack is one loopback-only container on one machine
(ADR-0001), so the constraint is recorded rather than designed around, and a clustered Redis
would need a prefix or a second instance instead. The live pgvector suite has the same defect
and does not get the same cure, because Postgres isolation is a different mechanism (a database
or a schema plus `search_path`, and `docker/postgres/init.sql` applied to it):
`memory_contract.check_empty_search` asserts `search(k=5) == []` over the whole `memories` table
and `check_ranks_by_similarity` asserts an exact top-2, both of which hold today only because
that table happens to be empty. That was measured rather than assumed: with Postgres up and the
table empty the suite passes, and inserting a single real (non `contract-`) memory row reddens
`check_empty_search` at `memory_contract.py:36` with no code changed. Recorded in
[docs/refinements/index.md#repo-gates](../refinements/index.md#repo-gates).

## Addendum (2026-08-06): the live pgvector run gets a Postgres database of its own

The addendum above closed the Redis half of this defect and named the Postgres half as the
deferral it opened. That half is closed now, on the same reasoning and with a different mechanism,
because Postgres has no numbered-database equivalent of Redis's `SELECT n`.

**The failure, reproduced before it was fixed.** With the compose Postgres up and the `memories`
table empty, `uv run pytest -m integration --no-cov packages/memory` passed. Inserting one real
(non `contract-`) row, `the user takes their coffee black`, turned it red at
`memory_contract.py:36`, `assert list(await store.search((1.0, 0.0, 0.0), k=5)) == []`, with no
code changed. So the suite was reporting on the table's contents, and the first memory the brain
actually recorded would have blamed a correct adapter. It had stayed green only because this
machine's table was empty, which is not a property of the code.

**Decision: the live run opens the `cortex_contract` database, and the brain never does.**
`brain/packages/memory/tests/live_postgres.py` owns the whole mechanism, as `live_redis.py` does
for Redis: `live_dsn()` rewrites the configured `CORTEX_MEMORY_DSN`'s path onto that database (the
database name in a DSN path is what a Postgres URL carries where a Redis URL carries the index),
and `reset()` empties it with `TRUNCATE TABLE memories` where the Redis helper calls `FLUSHDB`.
The suite resets before the run and after every check, so each check starts from the empty store
the in-memory fake already grants it, and the fake and the real adapter run the identical suite.
The checks no longer return their ids for a caller to sweep, which removes the same kind of
coupling the Redis change removed: a test that knows how to clean up after the adapter.

**Why a database and not a schema plus a `search_path`.** A schema is the cheaper isolation on
paper: one connection string, one `CREATE EXTENSION` for the whole database, no bootstrap of a
second catalog. It was rejected on its failure mode. `PgVectorMemoryStore`'s SQL names the table
unqualified (`FROM memories`, `INSERT INTO memories`), so under a schema every query's destination
is decided by a session setting rather than by the connection: a `search_path` that fails to
apply, through a driver that drops the option, a pooled connection that resets it, or a typo,
silently lands the whole suite on `public.memories`, and that includes this module's `TRUNCATE`.
The isolation would then be doing exactly what it exists to prevent, and doing it quietly. With a
database, a wrong destination is either the brain's database, which `live_dsn` refuses by name, or
one that does not exist, which fails to connect. The other half of the argument is the bootstrap:
`docker/postgres/init.sql` is unqualified too, so a schema needs an edited copy of it, which is a
second definition of the schema the adapter is tested against, free to drift from the first. A
database needs no copy at all; pgvector being installed per database rather than per schema is the
cost, and it is one line of the same file.

**The bootstrap is the same file, included rather than restated.**
`docker/postgres/live-contract-db.sql` is a second initdb script beside `init.sql`. It runs
`CREATE DATABASE cortex_contract`, `\connect`s to it, and `\i`s `init.sql`, so the contract
database gets the extension, the table, and the index the brain's database gets, from the one file
that defines them.

**A machine whose data dir predates that file gets no database, and the run refuses rather than
falling back.** An initdb script never re-runs on an existing data dir, which is the same
constraint the runbook's in-place column migrations already live with. `live_postgres.connect()`
answers both ways the database can be absent before any check runs: `InvalidCatalogNameError` from
the pool, and a database that exists without the bootstrap, which it catches by asking
`to_regclass('memories')`. Both fail the run with the two statements that create it. Auto-creating
it from the test was rejected: it would be a test provisioning a database against whatever DSN it
was handed, and applying the bootstrap would mean the harness reading a `docker/` file out of the
repo, both to spare a human one paste that the runbook already carries.

**Nothing about this reaches production configuration.** The adapter is untouched, no store gained
a schema, a table prefix, or a database argument, `docker-compose.memory.yml` still points
`CORTEX_MEMORY_DSN` at `cortex`, and no new environment variable exists to be set wrongly. The
database name lives in one test-only module. Two guards make the truncate safe by construction:
`live_dsn` refuses a `CORTEX_MEMORY_DSN` that already names `cortex_contract` (that would mean the
brain is pointed at the database `reset` empties) and refuses a scheme that carries no database in
its path, and `reset` re-reads `current_database()` from the pool it was handed and refuses to
empty anything else, so the check sits where the damage would be rather than only where the DSN
was built. The `pg-backup` sidecar dumps `-d cortex`, so the contract database is not in the
plug-and-play export either.

**Evidence (agent, Docker plus the real compose Postgres, 2026-08-06).** With the planted real
memory still in the brain's table, the suite goes from that one failure to `1 passed`, and the
brain's table is byte-identical across the run: one row, `md5` of its serialized columns
`24dde1e28a64319ad94d3d4765de7442` before and after, while `cortex_contract` is left empty. All
four refusals were fired rather than reasoned about, each with the exact message quoted in the
runbook: the brain pointed at `cortex_contract` (`names database cortex_contract, which the live
contract run reserves and empties`), a `mysql://` DSN (`names no postgresql:// database`), `reset`
called on a pool opened against `cortex` (`refusing to empty database 'cortex'`, with the brain's
row still there afterwards), and the two unbootstrapped states (`DROP TABLE memories` and
`DROP DATABASE cortex_contract`), both of which print the two `CREATE DATABASE` / `psql -f`
statements. The initdb path was proven on a fresh data dir rather than assumed, by bringing the
same compose up under a throwaway project name: the entrypoint logs
`running /docker-entrypoint-initdb.d/live-contract-db.sql`, `\l` lists `cortex_contract`, and
`\dx vector` plus `\d memories` show the extension, the six columns, and `memories_scope_idx`. The
suite still has teeth in its new database: reporting the score as raw distance rather than
`1 - distance` reddens `check_ranks_by_similarity` at `assert hits[0].score > hits[1].score`.

**Known limits.** A schema change to `init.sql` now has two databases to reach on an existing data
dir, not one; the runbook's upgrade section says so, and both get the same `ALTER TABLE ... IF NOT
EXISTS` statements. And the isolation reaches contract runs only: the seam-level live tests drive
the running brain, so they necessarily use the brain's own stores. Those were read rather than
assumed on 2026-08-06 and assert relative properties (the reminder seam filters its own
`reminder_id`, the tools registry asserts membership in the tool list, the email reader asserts
`INBOX` is among the folders), which is the property that makes sharing survivable when owning the
store is not an option.

## Addendum (2026-08-10): the shuffle re-run wider, still finding nothing, still not a gate

The deferral above was checked on 2026-08-09 by a sweep that **read** the tree, which cannot settle
a trigger whose subject is what happens when the order changes. It was re-measured on 2026-08-10 by
running it, with the plugin still supplied for the run only so neither lockfile moved:
`uv run --with pytest-randomly pytest -p randomly --randomly-seed=N` from `brain/` at seeds 1, 2, 3,
20260810 and 987654321 (2306 tests, 65 integration-marked deselected) and from `scripts/` at the
same five seeds (400 tests). Ten runs, all green, each still reaching the 100% line and branch
coverage both `addopts` demand. `--collect-only` proves the order really moved: seeds 2 and 3 list
the same 2306 node ids with none in the same position, seeds 1 and 2 list the same 400 in `scripts/`
with two. The scope is wider than the 2026-07-18 check in two ways, the whole workspace at every
seed rather than `packages/core` at three, and `scripts/`, which had never been shuffled.

**The two failure kinds were separated in advance, and neither appeared.** A test failing on a
sibling's leftover state is the order dependency the trigger names; a test failing because the
plugin reseeds `random` per test is a property of the plugin. The second has no reachable consumer
here: the only draw in the gated Python is `contrast.py`'s bootstrap resampler, which holds its own
`random.Random(seed)` rather than the module global, and the per-turn marker id in
`cortex_core.untrusted` comes from `secrets.token_hex`, which no seed reaches. So the standing-gate
cost is the first half alone, a different order per run and a seed to recover from a log.

**The recommendation is recorded, not taken**, a gate change being the maintainer's call: do not
adopt it now. Ten shuffled runs found nothing for it to catch, and the reproducibility cost is
real. The middle option worth naming if it ever looks worth it is a fixed `--randomly-seed` in
`addopts`, one deterministic order that is not the collection order; it would have caught nothing
here either.

## Addendum (2026-08-11): the coverage run excludes build scripts, which newer nightlies instrument

Decision 1 puts the branch-coverage step on nightly, and the rust CI job installs the channel
rather than a dated toolchain, so the step runs on whatever nightly exists the day it runs. That
drifted into a failure the local gate could not see. In CI the gate failed
`--fail-under-lines 100` with totals of 99.40% lines, 99.55% regions and 99.06% branches while the
same commit measured 100% on all four metrics here, every Rust test passing on both sides.

The whole difference is one new row. Holding cargo-llvm-cov at 0.8.7 and moving only the
toolchain, rustc 1.98.0-nightly (2026-07-01) omits Cargo build scripts from the report entirely,
and rustc 1.99.0-nightly (2026-08-10) instruments them: `crates/rpc/build.rs` appears at 41.18%
lines, 53.85% regions and 50.00% branches, adding 17 instrumented lines of which 10 are
unreachable, which is what carried the totals under the threshold.

**No test can reach that code, and the reason is structural rather than a gap in the suite.** That
build script regenerates the committed seam stubs only when `CORTEX_REGEN_PROTO=1` with `protoc`
on `PATH`; normal builds and CI take its early return, as the script's own module doc says. It
runs at build time under cargo, not inside a test binary, so no test in the workspace can execute
the regeneration arm. A build script is build tooling, and gate 3's rule that real toolchain calls
live behind manually run checks is the same rule read one level out.

So the coverage run excludes build scripts, `--ignore-filename-regex '/_generated/|/build[.]rs$'`,
which widens decision 4's exclusion from generated code to the generator alongside it. The pattern
spells the dot as a character class rather than a backslash escape because it travels through a
just recipe line before llvm-cov sees it. **Measured rather than assumed:** under 1.99.0-nightly
the exclusion returns the totals to 1655 lines, 232 functions, 1311 regions and 104 branches with
none missed, which are exactly the figures the older nightly reported before the drift, and the
measured file set is identical to that run's, so the exclusion drops the build script and nothing
else. Both nightlies now pass the gate and `coverage_gate.py`. The shell's build script
(`body/app/src-tauri/build.rs`) never entered the measurement, its workspace being excluded, and
the pattern covers it regardless.

What this does not fix is the drift itself: the channel stays unpinned, so the next upstream
instrumentation change can break the gate again with no change in this repo, and it will surface
on whichever pull request runs next rather than on the commit that caused it. Pinning trades that
for a nightly that silently goes stale and that dependabot cannot bump, since the toolchain is a
channel string rather than an action SHA. That trade is the maintainer's call and is recorded
in [R-274](../refinements/tasks/274-unpinned-nightly-drifts-the-coverage-gate.md).

## Addendum (2026-08-16): the coverage step names its toolchain, and the channel stays a channel

The addendum above closed one instrumentation change and left the drift that delivered it open.
Reopening it began by re-deriving the claim rather than trusting it, and every half of it still
holds. The rust job installs `toolchain: nightly` in `.github/workflows/ci.yml`, a channel with no
date. `check-body` invokes `cargo +nightly llvm-cov`, the same channel by name.
`docs/runbooks/local-dev-wsl.md` records `rustup toolchain install nightly` and
`cargo install cargo-llvm-cov` with no version on either. Nothing ties the two sides together. The
divergence is not a hypothesis either: this machine's `nightly` alias resolves to rustc
1.98.0-nightly (2026-07-01) while CI resolves whatever exists on the day it runs, so the two sides
have been measuring branch coverage with compilers six weeks apart ever since that incident. One
sentence of the addendum above is amended by this one, and only for the rule it broke: it said the
trade was "recorded open", which writes a status somewhere other than the task's own Status line.

**What landed: the step names what it is about to measure with.** `check-body` now runs
`rustc +nightly --version` and `cargo +nightly llvm-cov --version` immediately before the
measurement. One place covers both sides, because CI runs that same recipe rather than its own
copy of the command, and `just check` buffers the recipe's output and prints it, so a local run
and a CI run carry the same two lines. Two things follow beyond the log. A machine with no nightly
installed now fails at a probe that names the toolchain rather than part way through a
measurement. And cargo-llvm-cov's version is recorded beside the compiler's, which the earlier
incident could only hold constant by hand.

**Decision: the toolchain stays a channel, and that is a decision rather than a further
deferral.** Three arguments, the first of which the deferral did not have.

*A dated pin carries an expiry that nobody is scheduled to service.* Nightly runs two releases
ahead of stable and Rust ships stable every six weeks, so a nightly pinned today sits roughly
twelve weeks ahead of the stable the rest of `just check` compiles with, and is overtaken by it
twelve weeks after that. Past that point the coverage step compiles the body under an older
compiler than every other step in the gate, so the first newly stabilized feature the workspace
adopts passes fmt, clippy and `cargo test` and fails only under coverage. That failure reads as a
coverage fault and is not one, which is exactly the confusion this entry exists to remove,
reintroduced by its own fix and on a clock. The gap is measurable on this machine rather than
assumed: stable here is 1.96.1 (2026-06-26) and the dated nightly beside it is 1.99.0-nightly
(2026-08-10), three releases apart.

*A pin on the compiler alone would sell a reproducibility the step does not have.* The coverage
step has two moving parts, not one. CI installs the tool as `tool: cargo-llvm-cov` with no version
and the runbook says `cargo install cargo-llvm-cov` with no version, so both sides resolve
whatever is current there too, and the earlier measurement had to hold the tool at 0.8.7 by hand
before it could say anything about the compiler. Pinning the tool as well is worse rather than
better: cargo-llvm-cov reads the profile data the compiler's LLVM writes, so it is the half that
has to track the compiler, and freezing it against a channel that keeps moving is this same
mismatch with the roles swapped.

*And the printing buys most of what the pin was wanted for.* Read again, the expensive part of the
incident was not that the toolchain moved. It was that neither log said which toolchain it was, so
telling a toolchain change from the commit under test meant installing a second nightly here and
bisecting against it. Two printed lines read side by side settle that in one pass. What a pin
would still buy is prevention, at the expiry above, and the trigger recorded for it was a *second*
instrumentation drift, which has not happened: there has been one.

**What this leaves open.** The versions are printed and no gate reads them. Neither side compares
its toolchain against the other's, nothing records which toolchain last measured green, and a CI
log ages out, so recovering that comparison after a future drift still means finding a log from
before it. Recorded as its own entry,
[R-275](../refinements/tasks/275-nothing-reads-the-printed-toolchain.md).
