# Fence the single-handoff claim across processes

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** A second process that can swap: a second brain replica, a CLI or worker sharing the Redis, or a supervisor sidecar that swaps itself.

Opened 2026-07-18 by a verification pass
over the brain-handoff conductor ([ADR-0030 addendum](../../adr/ADR-0030-brain-handoff.md)), which
found the residual undocumented rather than unknown. The one-GPU-one-handoff rule is
`SwappingModelManager.handoff_claim`, and it holds `self._handoff_claimed` as instance state, so
it binds **one process**; the store-side guard ADR-0030 names as the cross-process backstop is
`active()` read in `SwapConductor._prepare` and the record written two awaits later, a check
followed by an act rather than a claim, so two brain processes on one Redis could both read "no
handoff" and both evict the cortex. Not a live defect: the deployment runs exactly one brain
process (one `brain` service in `docker/docker-compose.yml`, no replicas), so the in-process
claim is the whole population of claimants, and the loser of either guard is refused before
anything is drained or evicted and told a handoff is already running rather than that the swap
broke. **Costs a port change, not a tweak:** `put` cannot express "only if no handoff is active",
so `HandoffStore` gains a fenced claim verb, implemented in Redis as an atomic `SET
cortex:handoff:active <id> NX` issued before the record write or as a Lua script (a MULTI/EXEC
transaction cannot branch on an intermediate reply). It also needs an expiry story, because a
fenced claim whose holder dies wedges every other process until the key is cleared by hand,
where a stranded record today is deliberately TTL-free and settled by the next boot recovery: a
lease (TTL plus a heartbeat) or a user id recovery can recognize. Then the fake carries the
same semantics, the contract suite gains a two-concurrent-claimants case, and `_prepare` calls
the claim instead of `active()`. **Trigger:** a second process that can swap (a second brain
replica, a CLI or worker sharing the Redis, or a supervisor sidecar that swaps itself).
**Still not met as of 2026-07-18**, now that the supervisor sidecar exists: it performs no swap of
its own. The brain drives it through the port, its control API can only start, stop and report the
tiers its own env declares, and it holds no handoff state at all, so it is not a second claimant.

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
