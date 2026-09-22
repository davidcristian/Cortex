# The placer holds one flag for the whole card

**Status:** open, waiting for its trigger
**Area:** resource-governance
**Origin:** [ADR-0054](../../adr/ADR-0054-baseline-residency.md)
**Trigger:** The model host gaining a tier a deployment could correctly list beside the subagent
tier, meaning `ModelHostConfig.tiers()` (`brain/packages/model_manager/src/cortex_model_manager/config.py`)
declaring a fourth `TierArgs` after `cortex`, `brain` and `subagent-gpu`; or a subagent roster entry
gaining a second GPU target beside `gpu_endpoint`. Check with
`grep -c 'TierArgs(' brain/packages/model_manager/src/cortex_model_manager/config.py`: 3 means
neither has happened.
**Verified:** 2026-09-17

The placer has a single flag for whether the GPU is available, while the residency record has one
entry per tier, so any missing tier closes GPU placement for the whole pool. The brain has no
declared mapping from a hosted tier id (`CORTEX_SWAP_EVICT_MODELS`, a model-host roster name) to the
GPU endpoint a roster entry dials (`CORTEX_SUBAGENTS_GPU_ENDPOINT`, a URL), and that mapping would
have exactly one possible value in every deployment this repo ships, so declaring it would add a
setting with only one correct value.

The cost of the single flag is a deployment that lists a tier the subagent pool never places on and
loses GPU placement it did not need, which is decode rate rather than correctness. The conservative
direction is deliberate, since refusing too little costs a dead load per spawn.

The fix is a declared tier id per roster entry, threaded into `PlacementRequest` so the placer can
skip one target rather than all of them. That is also what would reopen the declined
placement-aware CPU charging entry ([R-189](189-placement-aware-cpu-charging.md)).

## History

- 2026-08-09: Opened by the tier-outage close, one of the three entries it left behind.
- 2026-09-10: Checked against the tree and not fired. `SwapConfig.evict_models` still defaults to
  the empty tuple, and the one place `CORTEX_SWAP_EVICT_MODELS` is written is a comment in
  `docker/docker-compose.gpu.yml` naming the GPU-placed subagent tier, which is the single value the
  entry says the mapping would have.
- 2026-09-12: Checked again and not fired, and one cross-reference was stale. `VramBudgetPlacer` has
  `_gpu_closed`, one boolean read before the headroom arithmetic, against `BaselineTiers`' `_faults`
  dict of one entry per tier, and `PlacementRequest` still has a model id and three resource figures
  and no target. The roster's per-entry `gpu_endpoint` (`config_subagents.py`) is still the only
  address a GPU placement dials. The stale part was the last clause: R-189 does not wait on this
  condition, it was declined in 2026-07-16 and names a second GPU-capable executor as what would
  reopen it. Read against [R-199](199-the-retry-passs-start-guarded-but-not-ordered.md), they are not one defect seen
  twice.
- 2026-09-17: Checked again, still not fired, and the trigger restated, because as written it could
  only fire on a misconfiguration. `ModelHostConfig.tiers()` declares three tiers, so the only ids a
  deployment can list beside `subagent-gpu` are the cortex, the deep tier, or an id no roster has.
  `ResidencyPlan` refuses the first two at boot, since every reader of the list would start them
  (ADR-0030 decision 8), and an id no roster has closes the placer through `mark_unhosted`, which
  the runbook names as a misconfiguration to fix by dropping the id. The code is unchanged:
  `placer.py` still sets and reads `_gpu_closed` at lines 48, 61, 109 and 113.
