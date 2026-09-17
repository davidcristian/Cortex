# The placer holds one bit for the card

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** The model host gaining a tier a deployment could correctly list beside the subagent
tier, meaning `ModelHostConfig.tiers()` (`brain/packages/model_manager/src/cortex_model_manager/config.py`)
declaring a fourth `TierArgs` after `cortex`, `brain` and `subagent-gpu`; or a subagent roster entry
gaining a second GPU target beside `gpu_endpoint`. Recheck with
`grep -c 'TierArgs(' brain/packages/model_manager/src/cortex_model_manager/config.py`: 3 means
neither has happened.
**Verified:** 2026-09-17

The placer carries a single flag for whether the GPU is available, while the residency record holds
one entry per tier. Opened 2026-08-09 by the same close. Any missing tier closes GPU placement for
the whole pool, because the brain has no declared mapping from a hosted tier id
(`CORTEX_SWAP_EVICT_MODELS`, a model-host roster name) to the GPU endpoint a roster entry dials
(`CORTEX_SUBAGENTS_GPU_ENDPOINT`, a URL). Today that mapping would have exactly one possible value
in every deployment this repo ships, so declaring it would add a setting with only one correct value
in any shipped deployment. The cost of the coarse flag is a deployment that lists a tier the
subagent pool never places on and loses GPU placement it did not need, which is decode rate rather
than correctness, and the conservative direction is deliberate (refusing too little costs a dead
load per spawn). The fix is a declared tier id per roster entry, threaded into `PlacementRequest` so
the placer can skip one target rather than all of them. The trigger is a hosted tier a deployment
could correctly list beside the subagent tier, or a second GPU-capable executor, which is also
what would reopen the declined placement-aware CPU charging entry
([R-189](189-placement-aware-cpu-charging.md)). The trigger used to be any deployment naming more
than the subagent tier in `CORTEX_SWAP_EVICT_MODELS`, which no correct deployment can do while the
model host carries three tiers (the 2026-09-17 trail line).

## Trail

- 2026-08-09: Opened by the tier-outage close, one of the three entries it left behind. Any missing
  tier closes GPU placement for the whole pool, for want of any declared mapping from a hosted tier
  id to the GPU endpoint a roster entry dials, and the conservative direction is deliberate.
- 2026-09-10: read against the tree and still not fired. `SwapConfig.evict_models` still defaults
  to the empty tuple, so a shipped deployment names no tier at all, and no compose file in
  `docker/` sets `CORTEX_SWAP_EVICT_MODELS`: the one place it is written is a comment in
  `docker/docker-compose.gpu.yml` naming the GPU-placed subagent tier as the thing to list, which
  is the single value the entry says the mapping would have. The coarse flag is unchanged as well,
  and `residency_tiers.py` still carries the paragraph saying it holds one bit for the whole card
  rather than one per tier.
- 2026-09-12: re-derived and still not fired, and one cross-reference was stale. `VramBudgetPlacer`
  carries `_gpu_closed`, one boolean read before the headroom arithmetic, against `StandingTiers`'
  `_faults` dict of one entry per tier, and `PlacementRequest` still carries a model id and three
  resource figures and no target, so the fix the entry names is still a port change rather than a
  tweak. The roster's per-entry `gpu_endpoint` (`config_subagents.py`) is still the only address a
  GPU placement dials, and the roster alternate this repo ships omits it and falls back to the CPU
  endpoint, so the mapping the entry wants declared would still have one value here. The stale part
  was the last clause: the placement-aware CPU charging entry does not wait on that condition, it
  was declined in 2026-07-16 and names a second GPU-capable executor as what would reopen it, so
  the sentence now says reopen rather than wait.
  Read against [R-199](199-sweep-start-not-serialized.md) and they are not one defect seen twice.
  That one is an ordering residual between two control calls; this one is the width of one boolean.
  Neither fix touches the other's object, and the two triggers can fire independently.
- 2026-09-17: re-derived, still not fired, and the trigger restated, because as written it could
  only fire on a misconfiguration. `ModelHostConfig.tiers()` declares three tiers, and with every
  `CORTEX_MODEL_FILE_*` set it returns `cortex`, `brain` and `subagent-gpu` (run under
  `brain/.venv/bin/python`). So the only ids a deployment can list beside `subagent-gpu` are the
  cortex, the deep tier, or an id no roster has. `ResidencyPlan` now refuses the first two at boot,
  since every reader of the list would start them (ADR-0030 addendum of 2026-09-17). An id no
  roster has closes the placer through `mark_unhosted`, which the runbook already names as a
  misconfiguration to fix by dropping the id, so the one-bit width is not what costs that
  deployment anything. The code this entry
  describes is unchanged: `placer.py` still sets and reads `_gpu_closed` at lines 48, 61, 109 and
  113, `PlacementRequest` still carries a model id and three resource figures, and no commit since
  2026-09-12 touched either.
