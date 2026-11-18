# With escalation off nothing starts the GPU subagent servers

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0053](../../adr/ADR-0053-model-host-supervisor.md)
**Verified:** 2026-11-18

The model host starts one tier when it boots, the cortex (`boot_model` in
`brain/packages/model_manager/src/cortex_model_manager/server.py`). Every other tier is started by
the brain's residency code: boot recovery (`converge_residency`), the swap back
(`restart_evicted`) and the recheck pass (`recheck_tiers`), and each of them reads the ids in
`CORTEX_SWAP_EVICT_MODELS`. `build_swap` returns `None` when `CORTEX_ESCALATION` is off, which is
the default, so none of that code is built and nothing sends `POST /models/subagent-gpu/start`.

A deployment that names `CORTEX_MODEL_FILE_SUBAGENT_GPU` and lists both addresses in
`CORTEX_SUBAGENTS_GPU_ENDPOINT`, with no deep tier, has two servers in the model host's roster
that stay `stopped`. The placer still places two spawns on the GPU. Each is leased an address
that nothing serves, fails, and runs again on the CPU server. Neither boot warning reports it:
`warn_of_unmatched_gpu_servers` counts the evict list as agreeing whenever escalation is off.

The same happens under escalation to a server the evict list leaves out, and there the count
warning does report it.

## Reproduction

Drawn on 2026-11-18 with the base, gpu, memory, tools, subagents and model host loopback compose
files, both GPU addresses listed and `CORTEX_ESCALATION` unset. The brain was stopped before the
model host was recreated, so no earlier brain could start a tier.

- After the brain was listening and one recheck interval had passed, `GET /models/subagent-gpu`
  and `GET /models/subagent-gpu-2` both read `stopped`. The card read 11,241 MiB, against
  17,603 MiB with the three servers loaded.
- The brain's boot log had no warning.
- One delegated spawn logged `a GPU-placed subagent did not answer; re-running it once on the CPU`
  and was answered by `llama-subagent`.

Log: `~/.cache/cortex-run/2026-11-18/slot8/logs/escoff2.txt`. A first draw of the same check read both servers
`ready`, because the earlier brain, which had escalation on, started them when the model host was
replaced while it ran (`escoff.txt` beside it). The live checks of the two-server default on
2026-11-18 started each server by hand through the control API, so none of them reached this.

## What would close it

Decide what starts a peer tier when no handoff is configured, and build it. Two candidates:

1. The model host starts every subagent server of its roster after the cortex at boot, and its
   restart budget names them (`RestartPolicy(models=...)` names the cortex alone today). The brain
   then needs no control client with escalation off, as it needs none for the cortex.
2. The brain builds its model host adapter and the recheck pass whenever a GPU address is on the
   model host, and reads the servers to start from those addresses and not from the evict list.

Until one is built, a boot warning can say that the GPU addresses are on the model host and
nothing will start them.

## History

- 2026-11-18: filed by the audit of the two-server default, which drew the reproduction above.
