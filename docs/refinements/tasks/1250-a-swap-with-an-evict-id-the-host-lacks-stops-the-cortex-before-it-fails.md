# A swap with an evict id the host lacks stops the cortex before it fails

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Verified:** 2026-11-18

The servers of the GPU subagent tier have the ids `subagent-gpu`, `subagent-gpu-2` and so on, and
a deployment with a deep tier lists each of them in `CORTEX_SWAP_EVICT_MODELS`.
`warn_of_unmatched_gpu_servers`
(`brain/packages/orchestrator/src/cortex_orchestrator/gpu_servers.py`) compares how many ids the
list has with the server count and the addresses. It does not compare the ids, because the brain
does not read the model host's tier id (`CORTEX_MODEL_SUBAGENT_GPU`).

A list of the right length with one wrong id, for example `["subagent-gpu", "subagent-gpu-3"]`
beside two servers, passes the boot check. Then:

- The recheck pass logs `the model host does not serve this model at all` for the wrong id and
  closes GPU placement until the daemon is replaced (`mark_unhosted`). `subagent-gpu-2` is never
  started, and every spawn runs on the CPU.
- A handoff stops the cortex and `subagent-gpu`, reaches `host.stop("subagent-gpu-3")`, and fails
  with `the model host does not serve 'brain' at all, so this deployment cannot escalate until
  that tier is in its roster`. The deep tier is hosted, so the message names the wrong tier, and
  the cortex was unloaded and loaded again for a handoff that could not run. `SwapConductor` asks
  `unhosted` about the deep tier before anything is evicted, and does not ask about the evict
  list.

## Reproduction

`swap_in` (`brain/packages/core/src/cortex_core/residency_moves.py`) over
`ScriptedModelHost(running=["cortex", "subagent-gpu", "subagent-gpu-2"],
unhosted=["subagent-gpu-3"])` with that evict list raises `SwapFailedError` with the message
above and leaves `subagent-gpu-2` as the only model running. Run on 2026-11-18.

## What would close it

- Ask the host about every evict id where the deep tier is asked about, before the drain, and
  refuse the handoff with the id named.
- Word the `ModelNotHostedError` branch of `swap_in` from the id the host did not have.
- Let the boot check compare ids: `GET /health` on the model host lists every id of its roster in
  `models`.

## History

- 2026-11-18: filed by the audit of the two-server default, whose second server made a list of
  several ids the usual case.
