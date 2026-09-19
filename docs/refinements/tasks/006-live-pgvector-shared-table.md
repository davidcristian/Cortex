# The live pgvector run's shared memories table

**Status:** done 2026-08-06
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

Opened after the Redis fix in [R-005](005-live-runs-shared-redis.md), which does not reach
Postgres: isolation there means a dedicated database, or a schema plus a `search_path`, with
`docker/postgres/init.sql` applied to it.

The exposure was measured rather than assumed. `memory_contract.check_empty_search` asserts
`search(k=5) == []` over the whole table and `check_ranks_by_similarity` asserts an exact top two,
so with Postgres up and the table empty the suite passes, and inserting a single real (non
`contract-`) memory row makes `check_empty_search` fail at `memory_contract.py:36` with no code
changed.

Closed 2026-08-06, before the first real row appeared. What moved it was work queued behind it:
the judge reranker's cost fell twentyfold, so a deployment that really remembers things stopped
being hypothetical, and the widened recall corpus that decides that default would have written the
first real rows. The measurement above was reproduced first, exactly as written.

The live run now opens the `cortex_contract` database
(`brain/packages/memory/tests/live_postgres.py`, the Postgres counterpart of `live_redis.py`,
rewriting the DSN's path where that one rewrites the database index and calling
`TRUNCATE TABLE memories` where that one calls `FLUSHDB`), emptied before the suite and after
every check. `docker/postgres/live-contract-db.sql` creates it through compose by including
`init.sql` rather than restating the schema.

Two alternatives were rejected. Rewriting the two whole-table checks to assert inside a
`contract-` scope narrows what the contract proves, and the point of a suite that the fake and the
real adapter both pass is that they pass the same checks. A schema plus `search_path` fails badly:
the adapter's SQL is unqualified, so a `search_path` that does not apply would run the suite,
`TRUNCATE` included, against the brain's own table without reporting an error. A machine whose
data directory predates the bootstrap file instead gets a run that fails at startup, naming the
two statements that create the database.

Checked with a real row present in the brain's table: the suite passes, that table is
byte-identical across the run, and all four failure paths were triggered before being relied on.

## History

- 2026-08-03: Opened after the Redis fix, which does not reach Postgres, where isolation means a
  dedicated database or a schema plus a `search_path`.
- 2026-08-06: Closed before the first real row appeared. What moved it was work queued behind it:
  the judge reranker's cost fell twentyfold and the widened recall corpus would have written the
  first real rows. The live run opens the `cortex_contract` database, emptied before the suite and
  after every check and created by a second initdb script that includes `init.sql`. The schema plus
  `search_path` option was rejected on its failure mode.
