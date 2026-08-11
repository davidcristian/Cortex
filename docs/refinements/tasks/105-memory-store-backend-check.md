# A backend-failure check for MemoryStore

**Status:** landed 2026-08-11
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

The close needed a store that
could be taken away and found that only the embedder had one, so `InMemoryMemoryStore.fail_with`
landed as a twin of `HashEmbedder`'s rather than as a check both implementations answer. What
that leaves is the asymmetry the `Embedder` list exists to remove: "every failure crosses the
port as `MemoryStoreError`" is held by `test_pgvector.py` on one side and by one core test on
the other, twice rather than once, which is the arrangement `memory_contract.ALL_CHECKS` was
driven over both implementations to end. It is not free, because the checks take a bare
`MemoryStore` and the knob makes them take a pair, so all ten signatures move and the live
pgvector arm needs a way to break its own backend (closing the pool is the obvious one). **Fix
when it bites**, and the bite is a second implementation of the port, or an adapter found
letting a backend exception through, which is the thing a shared check would have caught.

**Closed 2026-08-11**, hours after it opened and **ahead of its trigger, neither arm of which
fired**: no second implementation of the port arrived and no adapter was found leaking. What
moved it is that the degradation the previous close installed rests on this guarantee, so an
unheld guarantee under a live catch is the gate that cannot fail AGENTS.md names as a defect,
and the cost the entry priced turned out to be the cost it named and no more. All ten checks
now take a `MemoryStoreUnderTest` pair (`store` plus an awaited `break_backend`), which is the
`EmbedderUnderTest` shape on the other port of the pair, and the eleventh is
`check_a_lost_backend_crosses_the_port_as_memory_store_error`: it writes a memory, takes the
backend away, and requires `add`, `search`, `count_candidates` and `delete_scope` each to answer
`MemoryStoreError` and not the driver's own exception type, naming the leaked type in the
failure message when one gets through. The knob is awaited because the real arm's break is I/O:
the fake is scripted with `fail_with`, and the live pgvector arm passes the adapter's own
`aclose`, so the pool the adapter owns is really closed and asyncpg's
`InterfaceError('pool is closed')` is raised inside each verb, leaving the adapter's own
wrapping as the only thing between it and the check. That made the live driver build a store per
check, since one check ends by destroying its own, and `aclose` is idempotent so the broken arm
still closes exactly once. Both arms are green and neither implementation leaked, which is the
honest outcome for a port whose two implementations were each already tested for this in their
own suite; what the list ends is that they were tested for it twice rather than once. Proven
able to fail on both arms before being trusted: `InMemoryMemoryStore._guard` rewritten to raise
`RuntimeError` reddened the fake arm alone (`add let a RuntimeError through instead of
MemoryStoreError`, one failed and ten passed), and `PgVectorMemoryStore.search` narrowed to
catch only `asyncpg.PostgresError` reddened the live arm alone (`search let a InterfaceError
through instead of MemoryStoreError`, the ten checks before it having passed against real
Postgres), each restored and each re-run green. **Nothing opened in its place**, and the one
bound worth stating is that the live knob is a closed pool, so what it exercises is the
`InterfaceError` arm of the adapter's `_WRAPPED`: the socket-level `OSError` arm is held by the
stopped-container run recorded at [ADR-0008](../../adr/ADR-0008-memory-v1.md) and the server-side
`PostgresError` arm by the canned-row suite in `test_pgvector.py`, so all three are held and
only one of them by this check.

## Trail

- 2026-08-11: Opened by the unavailable-memory close, which needed a store that could be taken away
  and found that only the embedder had one, so `InMemoryMemoryStore.fail_with` landed as a twin of
  `HashEmbedder`'s rather than as a check both implementations answer.
- 2026-08-11: Closed the same day, hours after it opened by the entry's own account and an hour
  after by the index ledger's, and ahead of a trigger neither arm of which fired, taking the area
  from 9 to 8 with nothing opening in its place. What moved it is that
  the degradation the earlier close installed rests on this guarantee, so leaving it unheld is the
  gate that cannot fail. Neither implementation was found leaking, so it records a guarantee held
  rather than a defect fixed, and the check was proven able to fail on both arms before it was
  trusted.
