# Fence the single-handoff claim across processes

**Status:** declined 2026-08-18
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Opened 2026-07-18 by a verification pass over the brain-handoff conductor
([ADR-0030 addendum](../../adr/ADR-0030-brain-handoff.md)), which found the residual undocumented
rather than unknown. The one-GPU-one-handoff rule is a flag on one object in one process (today
`HandoffClaim`, split out of the manager since this was written, over the residency board's own
condition), and the store-side guard ADR-0030 names as the cross-process backstop is `active()`
read in `SwapConductor._prepare` with the record written two awaits later, a check followed by an
act rather than a claim. Two brain processes on one Redis could both read "no handoff" and both
evict the cortex. All of that was re-derived on 2026-08-18 and is still exactly what the tree says.

**Declined, because the fence cannot deliver the property it is named for.** It is one guard out of
five, and the other four are in-process state on the same object: the GPU lease is an
`asyncio.Lock`, the residency record and the condition every acquire queues on are `ResidencyBoard`
instance state, the missing-peer record is `StandingTiers`, and the placer's VRAM ledger is a pair
of instance floats
([residency.py](../../../brain/packages/core/src/cortex_core/residency.py),
[residency_board.py](../../../brain/packages/core/src/cortex_core/residency_board.py),
[placer.py](../../../brain/packages/core/src/cortex_core/placer.py)). The swap wiring says as much
in its own header: the manager must be a single instance because a second one would be a second
lease. Two brain processes on one Redis would double-lease the GPU, publish contradicting residency
to two seams and charge the same card twice, fenced claim or not. Landing the fence alone would put
a cross-process-looking guard at the one place a reader checks while everything under it stayed
single-process, which is a worse record than the honest state today.

**And the fix is not the `SET NX` this entry sketches.** `active()` self-heals: a pointer left
dangling, or naming a terminal record, reads as no handoff and mutates nothing
([handoffs.py](../../../brain/packages/session/src/cortex_session/handoffs.py)). A bare `NX` on the
active key loses that, so a stale pointer would refuse every handoff until a human cleared it.
Keeping the self-heal inside an atomic claim means a Lua script that reads the pointer, reads the
record it names and claims only when it is absent or terminal, plus the ownership or lease story
this entry already admits it needs so recovery can tell its own strand from a live one. That is a
second distributed-concurrency protocol beside the schedule store's, built for a claimant
population of one.

**When a second claimant is actually proposed, this is not the work.** The work is a
distributed-residency decision record covering the lease, the board, the tier record and the
ledger, with the fenced claim as one of its consequences. Nothing in this repo can produce that
claimant today: the deployment declares one `brain` service with no replicas, and the supervisor
sidecar performs no swap of its own, its control API being able only to start, stop and report the
tiers its own env names. The trigger this file carried is recorded at the origin decision instead,
where the reopening argument now lives.

## Trail

- 2026-07-18: Opened by a verification pass over the brain-handoff conductor that found no new
  correctness defect but two deferrals nobody had written down, which under the doc-first Definition
  of Done is itself the violation; the area went 4 to 5. It is not a live defect, the deployment
  declaring one `brain` service, and it is not cheap either, which makes it a fourth entry whose
  "behind the unchanged port" reading would have been wrong.
- 2026-07-18: Re-checked once the supervisor sidecar existed and the trigger was still not met, the
  sidecar performing no swap of its own.
- 2026-08-09: A trigger sweep of the index's fix-when-it-bites bucket read that bucket against the
  tree and fired nothing. This entry was named there among the ones whose triggers are
  live-observation shaped, a deployment doing something rather than a file saying something, so no
  reading of the code settles it.
- 2026-08-18: Declined on a re-derivation of the tree. Every claim in it held, one identifier having
  moved into `residency_claim.py`, and the close rests on scope rather than on staleness: fencing
  one of five in-process guards buys no cross-process safety, and the atomic claim that preserves
  the self-heal is a Lua script plus an ownership story rather than an `NX`. The trigger moved to
  the origin decision's addendum, which a closed task may not carry.
