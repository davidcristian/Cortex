# A booted subagent server the evict list leaves out stays loaded through a handoff

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0053](../../adr/ADR-0053-model-host-supervisor.md)
**Verified:** 2026-11-18

The model host starts every GPU subagent server of its roster at boot (`boot_models` in
`brain/packages/model_manager/src/cortex_model_manager/server.py`). A handoff to the deep tier
stops the cortex and the ids in `CORTEX_SWAP_EVICT_MODELS`, and no other server. A deployment that
names `CORTEX_MODEL_FILE_SUBAGENT_GPU` and a deep tier, and leaves a server out of the evict list,
keeps that server on the card while the deep model loads.

`warn_of_unmatched_gpu_servers`
(`brain/packages/orchestrator/src/cortex_orchestrator/gpu_servers.py`) reports it when
`CORTEX_SUBAGENTS_GPU_ENDPOINT` lists the servers, because the address count and the evict count
then differ. It reports nothing when the brain lists no address on the model host and the evict
list is empty: both counts are 0, and the brain does not read which servers the host's roster has.
When the free memory that is left is under what the deep tier declares, the fit check fails the
handoff, and its line does not name the subagent servers as the cause.

This is read from the code on 2026-11-18. It has not been drawn on the card.

## What would close it

At boot, with escalation on, the brain reads the host's roster from `GET /health` and logs a
warning for each id that is not the cortex, not the deep tier and not in the evict list. A draw
of the configuration above comes first, to record what the handoff logs today.

## History

- 2026-11-18: filed when the model host began to start the GPU subagent servers at boot.
