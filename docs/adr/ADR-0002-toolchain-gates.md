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
[docs/refinements/repo-gates.md](../refinements/repo-gates.md) with its trigger: a test that
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
[docs/refinements/repo-gates.md](../refinements/repo-gates.md).
