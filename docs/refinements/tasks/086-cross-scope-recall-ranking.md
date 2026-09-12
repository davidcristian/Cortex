# Cross-scope recall ranking

**Status:** open, dead until a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** Something writes durable global facts under scoping.
**Verified:** 2026-09-13

Recorded inside the per-session and namespaced scoping entry, which named it in the sentence listing
what stayed behind the same seams when that scoping landed:

> Remaining behind the same
> seams: a **session+global union** read policy (dead until something writes durable global facts
> under scoping), **per-scope retention/eviction**, and **cross-scope recall ranking**.

## Trail

- 2026-07-06: Named as one of three refinements left behind the `MemoryScope` seam when per-session
  and namespaced scoping landed. The index's pickup order pairs it with the session and global union
  read policy, on the reason that nothing writes durable global facts under scoping yet.
- 2026-09-13: Re-derived, and the seam this was filed behind is the wrong one. Weighting a hit by
  the scope it came from is not a `MemoryScope` refinement: that policy only chooses which
  namespaces recall reads, and the weighting happens after the store has returned them. The seam
  that carries it is `RecallPolicy`, which landed a week after this entry was recorded
  ([ADR-0008](../../adr/ADR-0008-memory-v1.md) rerank addendum). It already hands a policy the
  whole candidate pool as `ScoredMemory` values, each of which carries `record.scope`, and takes
  back a `Ranking` naming the key it ordered by, so the work is a new policy beside the ones that
  ship plus one member in the `RankBasis` family, behind an unchanged port and an unchanged
  store. The trigger is unchanged and has not fired: with nothing writing durable global facts
  under scoping, every recall today ranks over one namespace or over all of them unfiltered, and
  a scope weight would have nothing to weigh.
