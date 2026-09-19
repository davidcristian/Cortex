# Per-provenance eviction

**Status:** open, dead until a consumer
**Area:** untrusted-content
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Trigger:** a source found hostile after the fact, whose derived memories must be forgotten by where they came from rather than by the scope they landed in.
**Verified:** 2026-09-19

It was recorded inside the context-preserving tainted-memory recording entry, in its list of what
remains behind the same seams (ADR-0019 deferred). The fragment, verbatim:
**per-provenance eviction**.

## Trail

- 2026-07-16: Recorded in the index as wanting `MemoryRecord` provenance first, which is why the
  first producer of claimed provenance did not unblock it. The memory area's bullet says the
  same from the other side, that a record stores only the taint bit and not ADR-0027 structured
  provenance, so this needs a different filter and stays fix-when-it-bites.
- 2026-08-06: The index recorded that the persisted per-turn taint marker the replayed-quotation
  entry needs is the one this entry and a precise recap refusal would both spend.
- 2026-08-16: Priced against the tree, given a trigger, and moved to the bucket the pricing says
  it is in. **Both halves of it are missing, where the record named one.** The 2026-07-16 line above has the filter
  half right, and understates it: `MemoryRecord` carries `id`, `text`, `embedding`, `at`, `scope`
  and `tainted` ([memory.py](../../../brain/packages/core/src/cortex_core/memory.py)), the
  Postgres table carries those same columns behind a single `memories_scope_idx`
  ([init.sql](../../../docker/postgres/init.sql)), and `Provenance` lives entirely in the pure
  core, on a ledger whose own docstring says it is reconstructed each turn and never persisted
  ([untrusted.py](../../../brain/packages/core/src/cortex_core/untrusted.py)), surviving a store
  only on the mid-turn `HandoffRecord` that expires in an hour. The half nobody wrote down is that
  there is no verb to filter with either: `delete_scope` is the only removal on the port, it is
  string equality on one namespace, and its single caller is the session-delete cascade
  ([ports_stores.py](../../../brain/packages/core/src/cortex_core/ports_stores.py),
  [memory_cascade.py](../../../brain/packages/core/src/cortex_core/memory_cascade.py)). So the
  origin's "behind the unchanged `MemoryStore` seam" heading does not hold for this item: a
  predicate delete is a port change, exactly as the sibling retention entry
  [R-085](085-per-scope-retention-eviction.md) found from the memory side.
- 2026-08-16: The code names this entry as its own unbuilt consumer, which is the strongest
  evidence for the bucket. `provenance.py` opens by saying that two consumers are designed for and
  neither is built, the confirmation card and per-provenance eviction of memories derived from one
  source, and `SourceKind` carries `attested` so that eviction by sender cannot sweep a URI
  spelling the same string. The design is finished and nothing has ever asked it to run.
- 2026-09-13: Re-read against the code, and every claim above still holds. `MemoryRecord` carries
  the same six fields, the `memories` table the same six columns under one `memories_scope_idx`,
  and `delete_scope` is still the only removal on `MemoryStore`, with `SessionMemoryCascade` its
  one caller. One verb joined the port since the reading above: `count_candidates` answers how many
  records a set of namespaces holds, which filters nothing, so the predicate delete this entry
  needs is still unwritten and the port change it implies is still a port change. Structured
  provenance does now survive one store, `HandoffRecord` carrying the whole `TaintLedger` including
  its `sources` for the length of a swap, which is the shape a durable marker would copy rather
  than a marker this entry could spend; that store is the subject of
  [R-077](077-provenance-across-stores.md). The trigger has not fired: no source has been found
  hostile after the fact here, and nothing evicts a memory by anything but its scope.
- 2026-09-19: Re-derived, and the trigger has not fired: every eviction in the brain's sources is
  a model leaving the card, and none removes a memory. `MemoryStore` still offers `add`, `search`,
  `count_candidates` and `delete_scope`, the last called only by `SessionMemoryCascade`;
  `MemoryRecord` still carries six fields and the `memories` table six columns under the one
  `memories_scope_idx`; and none of `memory.py`, `ports_stores.py`, `memory_cascade.py`,
  `provenance.py`, `handoff.py` or `init.sql` has changed since 2026-09-13. Two sentences above
  were wrong. The 2026-08-16 reading credits `SourceKind.attested` with keeping eviction by sender
  from sweeping a URI, but `attested` is true for `TOOL` and `MEMORY` and false for both `SENDER`
  and `URI`, so it cannot tell those two apart; what does is that they are separate kinds, which
  is the reason the enum's docstring gives for admitting them apart. The 2026-09-13 reading calls
  the handoff store the subject of [R-077](077-provenance-across-stores.md), which names that store
  as the one place a turn's ledger already persists; its subject is `ScheduledItem` and
  `SubagentResult`. The two entries do not wait on each other: this one needs a provenance column
  on memory records and a predicate delete on the port, and neither row R-077 names is a memory.
