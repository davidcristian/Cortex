# A forget deadlocks with a record that recalled two tainted rows

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md) decision 9
**Verified:** 2026-10-17

`PgVectorMemoryStore.add` takes a `FOR SHARE` lock on each recalled tainted row in the order its
subquery returns them, which is id order through `memories_pkey` on any table large enough for
the planner to use the index. The forget's `DELETE FROM memories WHERE tainted AND scope = ANY($1)`
locks rows in heap order through a sequential scan. When a turn that recalled two tainted rows
records while a forget's `DELETE` is scanning between them, each statement holds one row the other
needs: Postgres detects the deadlock and aborts one of them. In the reproduction it aborted the
`DELETE`, so the whole forget rolled back, every tainted row stayed, and the derived row was
stored; `delete_tainted` raises `MemoryStoreError` and the forget tool answers "the memory store
is unavailable, so nothing was forgotten". From the code, not run: the same answer follows a
failure on a later pass of `delete_tainted`'s repeat, although an earlier pass committed its
deletions.

Reproduction ([readings](../../readings/overlay-concurrency-flows.md)), on the `cortexn7` Postgres's
`cortex_contract` database: insert tainted rows `r2`, `x`, `r1` in that order and 5,000 untainted
rows, then `ANALYZE`. A third session holds `x` with `FOR UPDATE` for 2 s, which stops the `DELETE`
just after it locked `r2`, as a long scan would. Start the forget's `DELETE`, then 0.4 s later the
record's `INSERT ... SELECT` with `recalled` `['r1', 'r2']`. When the third session commits, the
`DELETE` fails with `ERROR: deadlock detected ... while deleting tuple (0,3)`, and `new`, `r1`, `r2`
and `x` are all left.

## What to do

1. Lock in one order on both sides: `ORDER BY id FOR SHARE` in the insert's subquery, and the
   tainted delete as `DELETE FROM memories WHERE id IN (SELECT id FROM memories WHERE tainted
   [AND scope = ANY($1)] ORDER BY id FOR UPDATE)`, so the lock node sits above the sort in both
   plans. The reproduction above with these two statements, run the same night, ended with the
   `DELETE` removing all three rows and the insert storing nothing, with no deadlock.
2. Add two `integration` tests to `memory/tests/test_pgvector_live.py`: the reproduction above,
   which a delete without the sort fails, and one on a table too small for the index, where the
   insert scans in heap order (`r2` before `r1`) and a held row with an id between `r1` and `r2`
   stops the sorted `DELETE` after `r1`, which an insert without the sort fails. Check that each
   fails on its mutation before trusting it.
3. State the lock order in ADR-0019 decision 9 and `docs/modules/brain-memory.md`.

## History

- 2026-10-17: filed by the closing audit of the recalled row check, reproduced with three `psql`
  sessions.
