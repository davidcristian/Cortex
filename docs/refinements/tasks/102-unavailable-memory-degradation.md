# A dead embedder or store kills the turn

**Status:** done 2026-08-11
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

Nothing in the brain caught `EmbedderError` or `MemoryStoreError`. `recall_memory_context` in
`turn_context.py` awaited `caps.memory.recall(...)` bare, `MemoryRecaller.recall` awaited `embed`
bare, and the engine's only handler was for `InferenceError`. So an embedding server that was
down or a Postgres that was unreachable did not cost a turn its recalled notes, it failed the
turn. That was the opposite of every other optional capability here: a dead tool sidecar is
worked around and reported (`SkipUnavailableToolRegistry`), a body that will not answer becomes a
recoverable tool result, and a subagent that cannot be admitted becomes an `ok=False` result.

It was recorded to wait for the first live turn taken against a stopped embedding server or a
stopped Postgres, which the memory runbook's teardown step makes easy to hit by accident, or for
the degraded-mode question being answered for some other optional capability.

**Closed 2026-08-11**, hours after it opened and before either of those happened, because the only
thing blocking it was a decision and the decision was available. The defect was reproduced by
running rather than by reading: a `TurnEngine` over the in-memory session store with a
`HashEmbedder` told to `fail_with` produced `TURN FAILED with EmbedderError`, where the same turn
with a live embedder finished in four events.

What shipped is [ADR-0008](../../adr/ADR-0008-memory-v1.md) decision 12. `EmbedderError` and
`MemoryStoreError` degrade in exactly two places and nothing else does: the read in
`_recalled_context` and the write in `record_exchange`. Those are also the two functions
`BrainPhase` shares with `TurnEngine`, so the deep model's phase degrades identically with no
second copy.

Both halves degrade, for opposite reasons. The read degrades because the turn genuinely has an
answer without its notes. The write degrades because raising cannot save it: the reply has
already streamed and the assistant message is persisted before `record_exchange` runs, so an
exception there loses the memory anyway and takes a turn the user has read with it. The exchange
itself is not lost, since it stays in the conversation; what is lost is a derived index entry,
which is why the write logs an `error` and the read a `warning`.

The failure is reported unconditionally on the module logger rather than on the opt-in recall
trail, since an outage visible only where `CORTEX_MEMORY_RECALL_AUDIT` is on would be the same
silence. The trail instead omits the line: no line is written for a recall that never happened,
so `pool == available` goes on meaning the pool was the whole readable store rather than
acquiring a `0 == 0` reading for a store nobody could reach. The user is told once, about the
read only, by one app-authored `StatusUpdate(state="forgoing")`. A lost recap gets no such
signal, because a recap compresses history the user can still scroll to, while a recalled memory
is knowledge from other conversations they cannot see and cannot supply.

## History

- 2026-08-11: Opened by the `Embedder` port's shared check list, which established that both
  implementations raise `EmbedderError` and nothing else, and then that nothing in the brain
  catches it or the store's error. It was filed rather than taken because the remedy was a
  decision. Filing it took the area to 8, and it moved the index cell but not the area header,
  which read 7 for the hours the entry was open.
- 2026-08-11: Closed the same day, taking the area back to 7 and then to 9 on the two entries it
  opened in its place ([R-103](103-memory-data-error.md) and
  [R-105](105-memory-store-backend-check.md)), both residue of the close.
- 2026-08-11: The close drew a boundary and refused a placement: what degrades is the adapters'
  own wrapping and nothing else, so a policy's `ValueError` still fails the turn, and the catch
  went into the two core functions rather than into an adapter that also serves the delete
  cascade.
