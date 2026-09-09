# A pass that starts the cortex, and a verb an operator could reach for

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-09-09
**Trigger:** a cortex that stops while the brain and the model host both keep running, which is the
one state neither of the two boot starters covers, or a second visit to the runbook's step 2. Both
are operator events, so the cheap recheck is whether the surfaces have moved:
`brain/packages/core/src/cortex_core/residency_regain.py` still calls `host.status` twice and
`host.start` never, `proto/body.proto` still declares 16 RPCs across its two services with none of
them an operator command, and the model host's control API still offers the four routes it shipped
with (`/health`, `GET /models/{model}`, and start and stop, in
`brain/packages/model_manager/src/cortex_model_manager/api.py`).

Opened 2026-08-18 by the close of [116](116-reconciliation-without-a-turn.md), which landed the
reading and deliberately not the write. The regain
([residency_regain.py](../../../brain/packages/core/src/cortex_core/residency_regain.py)) detects a
cortex that is serving again and republishes residency, so the runbook's residency recovery is its
step 2 alone, one `POST /models/cortex/start` through the sidecar's control API, the remaining two
steps of the manual recovery covering a stuck handoff record and the confirming turn. What the pass
will not do is issue that start itself, so a machine whose cortex is genuinely down stays down until
somebody asks for it.

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

**Re-derived on 2026-09-08, and the state is narrower than the paragraphs above say.** The pass
still starts nothing: `regain_residency` calls `host.status` twice and `host.start` never, and
`sweep_tiers` beside it is the only half of the pass that starts anything, and only for the peers
named in `evict_models`. Two other places start the cortex with nobody asking, and both are
boot-scoped. The sidecar's own lifespan starts `boot_model` when the daemon comes up
([api.py](../../../brain/packages/model_manager/src/cortex_model_manager/api.py)), and the brain's
boot recovery starts the cortex and gates it ready
([swap_recovery.py](../../../brain/packages/core/src/cortex_core/swap_recovery.py)). Restarting
either container therefore already brings a down cortex back, and what nothing covers is a cortex
that dies while both containers keep running. The verb has nowhere to land yet either:
[proto/body.proto](../../../proto/body.proto) declares 16 RPCs across `BrainService` and
`BodyService` and none of them is an operator command, and the control API is still the four routes
it shipped with.

**One number in the cost argument above is true only of the shipped configuration.**
`TierHealer.aclose`'s docstring says a pass is at most two control calls, and that holds while
`CORTEX_SWAP_EVICT_MODELS` is unset, which is the shipped default (`config_swap.py` gives
`evict_models` the empty tuple). With N peers named there a pass is at most 2N + 2 control calls,
one `status` and one `start` per peer plus the regain's two readings, so on the one deployment that
sets the variable the shutdown wait a gating start would lengthen is already longer than the
docstring's number. The bound itself is unaffected, every call being cut by the model host client's
own deadline; only the count is.

## Trail

- 2026-08-18: Opened by the close of [116](116-reconciliation-without-a-turn.md), which argued that
  a background pass may read the machine freely and may write to the card only under a fence, so
  the reading landed and the start did not.
- 2026-09-08: trigger checked and not fired, and the clause was narrowed to surfaces a reader can
  count rather than events nobody records. The readings: `regain_residency` makes two `status` calls
  and no `start`; `proto/body.proto` declares 16 RPCs, none an operator command; the model host's
  control API declares four routes; `evict_models` defaults to the empty tuple, which is what makes
  `TierHealer.aclose`'s "at most two control calls" a true statement about the shipped stack and a
  wrong one about a deployment with GPU-placed peers.
