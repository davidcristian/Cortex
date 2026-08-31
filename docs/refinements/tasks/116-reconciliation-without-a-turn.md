# Reach the residency reconciliation without a turn

**Status:** landed 2026-08-18
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Opened 2026-08-09 by the entry above landing, and it is the half a boot id cannot answer. The
reconciliation fires on one event, a daemon naming a different boot, and at one place, the top of
`_swap_in`. Both are deliberate (a probe per `Health` was priced at up to 5.80 s against a 5 s
recheck, and converging speculatively bounces a co-resident plan's peers), and together they
leave two states unreachable. **The first is the expensive one.** After a restore that failed,
`_set_resident(None, RESIDENCY_LOST)` means `acquire` raises `ModelUnavailableError` for every
model, so no turn runs, so no handoff starts, so nothing ever reaches the reconciliation even
once the sidecar has genuinely been replaced and is serving the cortex again. That is why
`docs/runbooks/model-swap.md`'s manual recovery still ends by restarting the brain. **The second
is only a dot:** a boot that could not confirm the cortex publishes `RESIDENCY_BOOT_FAILED` and
stays amber if the cortex comes up a minute later by itself, with the lease deliberately left
permissive so turns still run. **What would close it:** a reconciliation on the refusal path
rather than only inside a swap, which is a cold path (a refused acquire has already failed, so a
`GET /health` there costs nothing anyone is waiting on) but is genuinely delicate, because
`_claim` holds the residency condition and would have to release it to do I/O, and because the
same refusal is reached mid swap while the deep model is loading, where converging would stop
the very load in flight. So it wants a gate on "no scope is active" and its own concurrency
argument, and possibly an operator-facing re-converge verb instead, which needs no lock
reasoning at all.

**What landed is not the shape above, and two things this entry said had aged.** The writer it
names is gone: `_set_resident` became `ResidencyBoard.publish` when the bookkeeping moved into
[residency_board.py](../../../brain/packages/core/src/cortex_core/residency_board.py) on
2026-08-09, and the mechanism it describes is otherwise exactly what the tree still did on
2026-08-18. The delicate refusal path it proposes is no longer the only option either, because the
fence it says such a thing would have to invent already exists: `TierHealer` runs a fenced pass
every `CORTEX_SWAP_TIER_HEAL_S` and the manager already leaves the card alone inside it while a
handoff is claimed or a scope is active.

So the regain rides that pass rather than the refusal
([residency_regain.py](../../../brain/packages/core/src/cortex_core/residency_regain.py)): while
the report says the GPU is not serving it reads the cortex and the deep tier and, when the cortex
is `READY` and the deep tier is off the card, publishes the standing residency again and reopens
the placer's GPU. Both halves the entry names are closed by the one reading, since neither state
is distinguishable to it: the expensive one, where every `acquire` was refused until a restart, and
the cheap one, where only the dot was wrong. No lock reasoning was needed on `_claim`, nothing is
converged, and nothing is started.

## Trail

- 2026-08-09: Opened by the residency entry above landing, as the half a boot id cannot answer: the
  reconciliation fires on one event and at one place, so a brain whose restore gave up refuses every
  acquire and the state that most needs reconciling is the one state that can never reach it, which
  is why the runbook's manual recovery still ends by restarting the brain. One out and one in, so
  the area count held at 7.
- 2026-08-09: A trigger sweep of the index's fix-when-it-bites bucket read that bucket against the
  tree and fired nothing. This entry reached that verdict inside a group rather than under its own
  name, the residency and model-manager entries each recent close opened, whose triggers are
  live-observation shaped, a deployment doing something rather than a file saying something, so no
  reading of the code settles them.
- 2026-08-18: Landed as a read-only regain on the fenced pass that already sweeps the peers, rather
  than as the reconciliation on the refusal path this entry sketched: it never converges (that
  would bounce a co-resident plan's peers and could stop a load in flight), it never starts
  anything, and it publishes only when the cortex is serving **and** the deep tier is off the card,
  which is the guard against handing a lease out onto a card that still holds two tiers. The write
  tests the fence under the residency condition, so a handoff claimed mid pass cannot be overwritten
  by a reading taken before it. Reasoning at the origin decision's residency-regain addendum, and
  the runbook's manual recovery no longer ends by restarting the brain. The follow-up it declined to
  bundle, a pass that also starts the cortex and the operator-facing re-converge verb, is
  [310](310-a-pass-that-starts-the-cortex.md).
