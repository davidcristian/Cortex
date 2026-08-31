# A pass that starts the cortex, and a verb an operator could reach for

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** A cortex that has to come back with nobody at the console, or a second visit to the
manual recovery where starting the tier by hand was the only thing left to do.

Opened 2026-08-18 by the close of [116](116-reconciliation-without-a-turn.md), which landed the
reading and deliberately not the write. The regain
([residency_regain.py](../../../brain/packages/core/src/cortex_core/residency_regain.py)) detects a
cortex that is serving again and republishes residency, so the runbook's manual recovery ends at its
step 2, one `POST /models/cortex/start` through the sidecar's control API. What it will not do is
issue that start itself, so a machine whose cortex is genuinely down stays down until somebody asks
for it.

**Why it was not bundled, in the two costs a next reader should re-derive rather than trust.** A
cortex start is a whole tier load, minutes at tier scale, and it is only worth anything if the pass
then gates readiness; `TierHealer.aclose` waits out the in-flight pass and its docstring states that
the wait is bounded by two control calls, so a gating pass would hold shutdown for
`CORTEX_SWAP_LOAD_TIMEOUT_S` instead. Starting without gating is cheap but writes nothing anybody
can read, since the next pass observes the result anyway. And the state this would act on is one
where a start has already failed twice inside the swap back, which makes the real question a retry
budget (how often, how many times, and what stops it retrying against a machine whose artifact is
missing) rather than a reading.

**The alternative the parent entry floated, and it needs no concurrency argument at all**: an
operator-facing re-converge verb, which would be an explicit request rather than a policy, and could
therefore be allowed to converge (stop the deep tier, start the cortex, gate it) where a periodic
pass must not. Its cost is a surface rather than a schedule: today nothing in
[proto/body.proto](../../../proto/body.proto) carries an operator command, so it is a seam decision,
and the alternative to inventing one is that the control API the operator already uses is the
sidecar's own.

## Trail

- 2026-08-18: Opened by the close of [116](116-reconciliation-without-a-turn.md), which argued that
  a background pass may read the machine freely and may write to the card only under a fence, so
  the reading landed and the start did not.
