# The live pgvector run's shared memories table

**Status:** landed 2026-08-06
**Area:** repo-gates
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-gates.md)

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
([brain-memory.md](../../modules/brain-memory.md)) and in its runbook
([memory-pgvector.md](../../runbooks/memory-pgvector.md)) so the failure is legible when it lands.

**Landed 2026-08-06 ([ADR-0002 addendum on the live pgvector database](../../adr/ADR-0002-toolchain-gates.md)),
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

## Trail

- 2026-08-03: Opened behind the Redis fix, which does not reach Postgres, isolation there being a
  dedicated database or a schema plus a `search_path`.
- 2026-08-06: Landed ahead of its trigger, taking the area from seven entries to six. What moved
  it was two pieces of work queued behind it rather than a failure: the judge reranker's cost fell
  twentyfold and the widened recall corpus would have written the first real rows. The live run
  opens the `cortex_contract` database, emptied before the suite and after every check and
  bootstrapped by a second initdb script that includes `init.sql` rather than restating it; the
  schema-plus-`search_path` option was rejected on its failure mode. One bookkeeping repair rode
  along: the index's standing-open bucket had never carried this entry, so it listed six items
  under a header that read seven from 2026-08-03, and the close makes them agree at six.
