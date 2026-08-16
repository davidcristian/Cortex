# Per-provenance eviction

**Status:** open, dead until a consumer
**Area:** untrusted-content
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Trigger:** a source found hostile after the fact, whose derived memories must be forgotten by where they came from rather than by the scope they landed in.

It was recorded inside the context-preserving tainted-memory recording entry, in its list of what
remains behind the same seams (ADR-0019 deferred). The fragment, verbatim:
**per-provenance eviction**.

## Trail

- 2026-07-16: Recorded in the index as wanting `MemoryRecord` provenance first, which is why the
  first producer of claimed provenance did not unblock it. The memory area's bullet says the
  same from the other side, that a record stores only the taint bit and not ADR-0027 structured
  provenance, so this wants a different filter and stays fix-when-it-bites.
- 2026-08-06: The index recorded that the persisted per-turn taint marker the replayed-quotation
  entry wants is the one this entry and a precise recap refusal would both spend.
- 2026-08-16: Priced against the tree, given a trigger, and moved to the bucket the pricing says
  it is in. **Both halves of it are missing, not one.** The 2026-07-16 line above has the filter
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
