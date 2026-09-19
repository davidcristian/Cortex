# A backend-failure check for MemoryStore

**Status:** done 2026-08-11
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

The degradation close ([R-102](102-unavailable-memory-degradation.md)) needed a store that could
be taken away and found that only the embedder had one, so `InMemoryMemoryStore.fail_with`
shipped as a twin of `HashEmbedder`'s rather than as a check both implementations answer. That
left "every failure crosses the port as `MemoryStoreError`" asserted twice, once by
`test_pgvector.py` and once by a core test, which is the duplication
`memory_contract.ALL_CHECKS` exists to end.

**Closed 2026-08-11**, hours after it opened and ahead of its trigger, because the degradation
the previous close installed rests on this guarantee, and an unproven guarantee under a live
catch is the check that cannot fail that AGENTS.md names as a defect.

All ten checks now take a `MemoryStoreUnderTest` pair (`store` plus an awaited `break_backend`),
matching the `EmbedderUnderTest` shape on the other port. The eleventh is
`check_a_lost_backend_crosses_the_port_as_memory_store_error`: it writes a memory, takes the
backend away, and requires `add`, `search`, `count_candidates` and `delete_scope` each to answer
`MemoryStoreError` rather than the driver's own exception type, naming the leaked type in the
failure message. `break_backend` is awaited because the real break is I/O: the fake is scripted
with `fail_with`, and the live pgvector run passes the adapter's own `aclose`, so the pool the
adapter owns is really closed and asyncpg's `InterfaceError('pool is closed')` is raised inside
each verb. That made the live driver build a store per check, since one check ends by destroying
its own, and `aclose` is idempotent so the broken store still closes exactly once.

Both implementations pass and neither leaked, so this records a guarantee proved rather than a
defect fixed. It was proved able to fail on both first: `InMemoryMemoryStore._guard` rewritten to
raise `RuntimeError` made the fake fail alone (`add let a RuntimeError through instead of
MemoryStoreError`, one failed and ten passed), and `PgVectorMemoryStore.search` narrowed to catch
only `asyncpg.PostgresError` made the live one fail alone (`search let a InterfaceError through
instead of MemoryStoreError`, the ten checks before it having passed against real Postgres). Each
was restored and re-run.

One bound is worth stating: the live break is a closed pool, so what this check exercises is the
`InterfaceError` branch of the adapter's `_WRAPPED`. The socket-level `OSError` branch is covered
by the stopped-container run recorded at [ADR-0008](../../adr/ADR-0008-memory-v1.md), and the
server-side `PostgresError` branch by the canned-row suite in `test_pgvector.py`.

## History

- 2026-08-11: Opened by the unavailable-memory close, which needed a store that could be taken
  away and found that only the embedder had one.
- 2026-08-11: Closed the same day, ahead of a trigger that had not fired, taking the area from 9
  to 8 with nothing opening in its place.
