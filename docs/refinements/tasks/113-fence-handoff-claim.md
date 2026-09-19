# Fence the single-handoff claim across processes

**Status:** declined 2026-08-18
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

The one-GPU-one-handoff rule is a flag on one object in one process (`HandoffClaim`, over the
residency board's own condition). The store-side protection ADR-0030 names for the cross-process
case is `active()` read in `SwapConductor._prepare`, with the record written two awaits later,
which is a check followed by an act rather than a claim. Two brain processes on one Redis could
both read "no handoff" and both evict the cortex.

**Declined 2026-08-18, because the fence cannot deliver the property it is named for.** It is one
guard out of five, and the other four are in-process state on the same object: the GPU lease is an
`asyncio.Lock`, the residency record and the condition every acquire queues on are
`ResidencyBoard` instance state, the missing-peer record is `StandingTiers`, and the placer's VRAM
ledger is a pair of instance floats
([residency.py](../../../brain/packages/core/src/cortex_core/residency.py),
[residency_board.py](../../../brain/packages/core/src/cortex_core/residency_board.py),
[placer.py](../../../brain/packages/core/src/cortex_core/placer.py)). Two brain processes on one
Redis would double-lease the GPU, publish contradicting residency to two clients and charge the same
card twice, fenced claim or not. Building the fence alone would put a cross-process-looking guard
at the one place a reader checks while everything under it stayed single-process.

The fix is also not the `SET NX` the entry sketched. `active()` recovers by itself: a pointer left
dangling, or naming a terminal record, reads as no handoff and mutates nothing
([handoffs.py](../../../brain/packages/session/src/cortex_session/handoffs.py)). A bare `NX` on
the active key loses that, so a stale pointer would block every handoff until a human cleared it.
Keeping that recovery inside an atomic claim means a Lua script that reads the pointer, reads the
record it names, and claims only when it is absent or terminal, plus the ownership or lease design
the entry already admitted it needs so recovery can tell its own stranded record from a live one.
That is a second distributed-concurrency protocol beside the schedule store's, for a claimant
population of one.

When a second claimant is actually proposed, the work is a distributed-residency decision record
covering the lease, the board, the tier record and the ledger, with the fenced claim as one of its
consequences. Nothing in this repo can produce that claimant today: the deployment declares one
`brain` service with no replicas, and the supervisor sidecar performs no swap of its own, its
control API being able only to start, stop and report the tiers its own env names. The reopening
argument is recorded at the origin decision.

## History

- 2026-07-18: Opened by a verification pass over the brain-handoff conductor
  ([ADR-0030](../../adr/ADR-0030-brain-handoff.md) decision 5), which found no new correctness
  defect but two deferrals nobody had written down; the area went 4 to 5.
- 2026-07-18: Re-checked once the supervisor sidecar existed, and the trigger was still not met.
- 2026-08-09: A trigger review of the index's fix-when-it-matters bucket read it against the tree
  and fired nothing. This entry was named there among the ones whose triggers describe a
  deployment doing something rather than a file saying something.
- 2026-08-18: Declined after reading the tree again. Every claim held, one identifier having moved
  into `residency_claim.py`, and the close rests on scope rather than on staleness.
