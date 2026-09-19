# Reach the residency reconciliation without a turn

**Status:** done 2026-08-18
**Area:** inference-model-manager
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)

The boot-id reconciliation ([R-114](114-reconverge-residency-on-restart.md)) runs on one event, a
daemon naming a different boot, and at one place, the top of `_swap_in`. Both are deliberate: a
probe per `Health` was priced at up to 5.80 s against a 5 s recheck, and converging speculatively
bounces a co-resident plan's peers. Together they left two states unreachable.

The expensive one: after a restore that failed, the board publishes `RESIDENCY_LOST`, so `acquire`
raises `ModelUnavailableError` for every model, so no turn runs, so no handoff starts, so nothing
reaches the reconciliation even once the sidecar has been replaced and is serving the cortex
again. That is why `docs/runbooks/model-swap.md`'s manual recovery ended by restarting the brain.
The cheap one: a boot that could not confirm the cortex publishes `RESIDENCY_BOOT_FAILED` and
stays amber if the cortex comes up a minute later by itself, with the lease deliberately left
permissive so turns still run.

**Closed 2026-08-18**, not in the shape the entry proposed. It had suggested a reconciliation on
the refusal path, which would have needed `_claim` to release the residency condition to do I/O
and its own concurrency argument. That was no longer the only option, because `TierHealer` already
runs a fenced pass every `CORTEX_SWAP_TIER_HEAL_S`, and the manager already leaves the card alone
inside it while a handoff is claimed or a scope is active.

So the regain runs on that pass
([residency_regain.py](../../../brain/packages/core/src/cortex_core/residency_regain.py)): while
the report says the GPU is not serving, it reads the cortex and the deep tier and, when the cortex
is `READY` and the deep tier is off the card, publishes the residency again and reopens the
placer's GPU. It never converges, never starts anything, and needed no lock reasoning on `_claim`.
Both states close on the one reading, since neither is distinguishable to it. The write tests the
fence under the residency condition, so a handoff claimed mid pass cannot be overwritten by a
reading taken before it.

One name in the entry had aged: the writer it called `_set_resident` became
`ResidencyBoard.publish` when the bookkeeping moved into
[residency_board.py](../../../brain/packages/core/src/cortex_core/residency_board.py) on
2026-08-09.

## History

- 2026-08-09: Opened by the residency close as the half a boot id cannot answer. One out and one
  in, so the area count held at 7.
- 2026-08-09: A trigger review of the index's fix-when-it-matters bucket read it against the tree
  and fired nothing. This entry got that result inside a group rather than under its own name.
- 2026-08-18: Closed as a read-only regain on the fenced pass. Reasoning at
  [ADR-0054](../../adr/ADR-0054-baseline-residency.md) decision 5, and the runbook's manual
  recovery no longer ends by restarting the brain. The follow-up it declined to include, a pass
  that also starts the cortex plus an operator-facing re-converge verb, is
  [R-310](310-a-pass-that-starts-the-cortex.md).
