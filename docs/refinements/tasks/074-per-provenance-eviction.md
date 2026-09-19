# Per-provenance eviction

**Status:** open, waiting for a consumer
**Area:** untrusted-content
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Trigger:** a source found hostile after the fact, whose derived memories must be forgotten by where they came from rather than by the scope they were stored in.
**Verified:** 2026-09-19

Left behind by [R-072](072-tainted-memory-recording.md): removing memories by the source they came
from.

Both halves of it are missing. A `MemoryRecord` has `id`, `text`, `embedding`, `at`, `scope` and
`tainted` ([memory.py](../../../brain/packages/core/src/cortex_core/memory.py)), the Postgres
table has those same columns behind a single `memories_scope_idx`
([init.sql](../../../docker/postgres/init.sql)), and `Provenance` lives entirely in the pure core,
on a ledger whose own docstring says it is rebuilt each turn and never stored
([untrusted.py](../../../brain/packages/core/src/cortex_core/untrusted.py)), surviving a store
only on the mid-turn `HandoffRecord` that expires in an hour. And there is no verb to filter with:
`delete_scope` is the only removal on the port, it is string equality on one namespace, and its
single caller is the session-delete cascade
([ports_stores.py](../../../brain/packages/core/src/cortex_core/ports_stores.py),
[memory_cascade.py](../../../brain/packages/core/src/cortex_core/memory_cascade.py)). So the
origin's heading that this sits behind the unchanged `MemoryStore` port does not hold: a predicate
delete is a port change, as [R-085](085-per-scope-retention-eviction.md) found from the memory
side.

The code names this entry as its own unbuilt consumer, which is the strongest evidence that what
it waits for is a consumer: `provenance.py` opens by saying that two consumers are designed for
and neither is built, the confirmation card and eviction of memories derived from one source.

## History

- 2026-07-16: Recorded as needing `MemoryRecord` provenance first, which is why the first producer
  of claimed provenance did not unblock it.
- 2026-08-06: The stored per-turn taint marker the replayed-quotation entry needs is the one this
  entry and a precise recap refusal would both use.
- 2026-08-16: Priced against the tree and given a trigger. Both halves are missing, where the
  record named one: there is no provenance on a memory record and no predicate delete on the port.
- 2026-08-16: `provenance.py` names this entry as its own unbuilt consumer. The design is finished
  and nothing has ever asked it to run.
- 2026-09-13: Read again and every claim holds. One verb joined the port since: `count_candidates`
  answers how many records a set of namespaces holds, which filters nothing. Structured provenance
  now survives one store, `HandoffRecord` holding the whole `TaintLedger` including its `sources`
  for the length of a swap, which is the shape a durable marker would copy rather than one this
  entry could use. The trigger has not fired.
- 2026-09-19: Checked again, and the trigger has not fired: every eviction in the brain's sources
  is a model leaving the card, and none removes a memory. `MemoryStore` still offers `add`,
  `search`, `count_candidates` and `delete_scope`, the last called only by `SessionMemoryCascade`;
  `MemoryRecord` still has six fields and the `memories` table six columns under the one
  `memories_scope_idx`; and none of `memory.py`, `ports_stores.py`, `memory_cascade.py`,
  `provenance.py`, `handoff.py` or `init.sql` has changed since 2026-09-13. Two sentences here
  were wrong. The 2026-08-16 reading credited `SourceKind.attested` with keeping eviction by
  sender from also removing a URI, but `attested` is true for `TOOL` and `MEMORY` and false for
  both `SENDER` and `URI`, so it cannot tell those two apart; what does is that they are separate
  kinds. The 2026-09-13 reading called the handoff store the subject of
  [R-077](077-provenance-across-stores.md), whose subject is `ScheduledItem` and `SubagentResult`.
  The two entries do not wait on each other: this one needs a provenance column on memory records
  and a predicate delete on the port, and neither row R-077 names is a memory.
