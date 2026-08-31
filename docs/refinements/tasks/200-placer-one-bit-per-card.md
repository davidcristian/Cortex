# The placer holds one bit for the card

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** A deployment naming more than the subagent tier in `CORTEX_SWAP_EVICT_MODELS`.

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
the placer can skip one target rather than all of them. The trigger is a deployment naming more than
the subagent tier in `CORTEX_SWAP_EVICT_MODELS`, or a second GPU-capable executor, which is the same
condition the placement-aware CPU charging entry waits on.

## Trail

- 2026-08-09: Opened by the tier-outage close, one of the three entries it left behind. Any missing
  tier closes GPU placement for the whole pool, for want of any declared mapping from a hosted tier
  id to the GPU endpoint a roster entry dials, and the conservative direction is deliberate.
