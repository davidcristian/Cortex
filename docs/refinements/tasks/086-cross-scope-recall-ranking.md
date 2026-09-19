# Cross-scope recall ranking

**Status:** open, dead until a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** One recall's pool can draw from more than one non-empty scope: the union read of
R-084 lands, or a store already holding per-session scopes is read under
`CORTEX_MEMORY_SCOPE=global`, whose unfiltered search mixes them.
**Verified:** 2026-09-19

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
- 2026-09-19: Re-derived. No consumer has appeared, and the seam finding of 2026-09-13 holds:
  `RecallPolicy.select` still receives `ScoredMemory` values carrying `record.scope`, `RankBasis`
  still has the six members `ECHO`, `EMBER`, `SPREAD`, `SWEEP`, `VERDICT` and `DEMUR`, and the one
  commit to `rerank.py` since then only restated which policies may return fewer than `k`. The
  closing claim above was wrong, though: an unfiltered recall is not a recall over one namespace. A
  scope is stamped on each row when it is written, so a store that ran under `session` and is then
  set to `global` holds one scope per earlier conversation plus `global`, and `GlobalMemoryScope`
  reads all of them into one pool. That pool has scopes to weigh without anything writing durable
  global facts, so the trigger no longer waits on the writer alone. It now fires when a single
  pool can mix scopes, by the union of R-084 or by that switch. Recorded in the ADR-0008
  policy-switch addendum.
