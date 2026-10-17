# A forget that fails on a later pass says nothing was forgotten

**Status:** open, actionable
**Area:** brain
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md) decision 9
**Verified:** 2026-10-17

`PgVectorMemoryStore.delete_tainted` repeats its `DELETE` until a pass removes nothing, and each
pass commits on its own. When a later pass raises, the sum of the earlier passes is dropped and the
`MemoryStoreError` reaches `UntrustedMemoryForget.invoke`, which answers "the memory store is
unavailable, so nothing was forgotten" although the first pass already deleted its rows.

Reproduction: a `Database` whose first `execute` returns `DELETE 2` and whose second raises
`asyncpg.DeadlockDetectedError`; `delete_tainted()` raises `MemoryStoreError` ("deleting the
tainted memories failed") after two passes, and the two removed rows are reported nowhere.

## What to do

1. Decide what the forget says then: the count already removed with a note that the rest may
   remain, or a retry of the failed pass. A port change (`delete_tainted` returning a partial
   count with the error) needs the fake and the contract test to follow.
2. Test the answer over a database fake that fails on the second pass.

## History

- 2026-10-17: filed by the closing audit of the recalled row check.
