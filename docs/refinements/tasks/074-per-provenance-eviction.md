# Per-provenance eviction

**Status:** open, fix when it bites
**Area:** untrusted-content
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Trigger:** unrecorded

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
