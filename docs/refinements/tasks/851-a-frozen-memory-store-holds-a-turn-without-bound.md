# A frozen memory store holds a turn without bound

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Verified:** 2026-10-13

ADR-0008 decision 12 answers a turn without its notes when the store is unavailable, but a store
that accepts connections and never answers is never reported unavailable. With Postgres frozen by
`docker pause`, a turn whose pool already held a connection sent no event and logged nothing for
the 100 s and 120 s its client waited; one that needed a new connection waited for asyncpg's
default 60 s connect timeout ([readings](../../readings/store-and-sidecar-outages.md#postgres)).
`PgVectorMemoryStore.connect` calls `asyncpg.create_pool(dsn)` with no timeouts.

A bound is harder than a timeout argument. `command_timeout`, and `asyncio.timeout` around each
statement, both left the turn hung: the timed out task waits in `PoolConnectionHolder.release`,
shielded, for `Connection._cancel` to deliver a cancel request to the frozen server, which has no
timeout. The withdrawn attempt is not in the tree.

## Reproduce

Run one turn so the pool holds a connection, `docker pause` the Postgres container, send a turn
and wait two minutes; `docker unpause` after.

## What to do

Run each statement as its own task, wait for it with `asyncio.wait` and a timeout, and on expiry
cancel it without awaiting it, holding a reference until it ends; or terminate the connection on
expiry. Either way, test it with a fake `Database` that never answers, and check it on a frozen
server, since the shielded release is invisible to a fake.

## History

- 2026-10-13: filed from the outage flows, after a timeout on each statement did not bound a turn.
