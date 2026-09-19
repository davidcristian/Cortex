# The real GPU-placed runtime mechanism

**Status:** done 2026-07-18
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

The plan was two live `llama-server` sidecars (GPU `-ngl 99` and CPU `-ngl 0`) in
`docker/docker-compose.subagents.yml`, per-container `--cpus` and `--memory` limits, and real
validation of a GPU-placed subagent. Two of the three shipped as written and one moved: ADR-0030
decision 3 put the GPU sidecar inside the `model-host` supervisor container, the one holding the
GPU reservation and the models mount, so the GPU-placed subagent is a hosted tier on :8083 with
`-ngl 99`, opt-in behind `CORTEX_MODEL_FILE_SUBAGENT_GPU`. The CPU sidecar stays its own container.

`CORTEX_SUBAGENTS_GPU_ENDPOINT` does not point at that tier by default, and saying it did was the
one wrong claim this entry shipped with. It defaults to the CPU server, which is the safe default,
since a deployment that has not named a GPU subagent artifact would otherwise route GPU-placed
spawns at a tier with nothing behind it. Opting in is three settings together, written in the gpu
override's checklist and in [subagents-cpu.md](../../runbooks/subagents-cpu.md): the artifact file,
`CORTEX_SUBAGENTS_GPU_ENDPOINT=http://model-host:8083`, and the tier's id in
`CORTEX_SWAP_EVICT_MODELS` so a handoff stops it first.

The limits shipped on both containers (`cpus`, `mem_limit`, `memswap_limit`, confirmed applied by
the runtime as `NanoCpus`, `Memory` and `MemorySwap`), with the CPU one's defaults set to the hard
twin of the brain's soft admission budgets. The granularity this costs is worth knowing: the
cortex, the deep model and the GPU subagent are processes in one cgroup, so there is one set of
limits covering all three. A per-model limit would want a container per model, which needs a
controller that can start containers, which is the docker-socket design ADR-0030 decision 3
rejected.

The GPU placement path ran for real on 2026-08-04 (readings in
[subagent budget](../../readings/subagent-budget.md), procedure in
[subagents-cpu.md](../../runbooks/subagents-cpu.md)). With the soft cap raised to 20 GB for this
card (8.7 GB of headroom against the shipped 5.5 GB request), two concurrent spawns of one roster
entry went one to the GPU tier and one to the CPU server: the tier's own `llama-server` log shows
exactly one task, 18 prompt tokens at 104.83 tok/s and 4 generated at 81.07 tok/s for 221.05 ms in
total, against 12536.83 ms for the sibling that overflowed. With the shipped soft cap of 14 GB both
spawns overflowed and the tier's task count did not move, so it can stay silent as well as fire.
The suite was proved able to fail first, by pointing the GPU endpoint at a closed port.

What is still owed is the container limit numbers, which are user-tunable placeholders, recorded at
[docs/host/gpu-tier-scale.md](../../host/index.md#gpu-tier-scale) with the mmap trap ADR-0012
records: a limit below the artifact size makes a load thrash rather than fail.

## History

- 2026-07-15: Extracted from the roadmap's deferred-refinements section, one of this area's three
  entries blocked on the Slice 11 lifecycle.
- 2026-07-18: Closed with the model-host sub-slice and in a different container than expected,
  recorded at [ADR-0012 decision 15](../../adr/ADR-0012-resource-governance.md) and
  [ADR-0053](../../adr/ADR-0053-model-host-supervisor.md).
- 2026-07-18: The audit round corrected two records. The close had been declared with two of its
  three required records, and the claim that `CORTEX_SUBAGENTS_GPU_ENDPOINT` points at the hosted
  tier was false, so the three-setting opt-in went into the gpu override's checklist and the
  subagents runbook.
- 2026-07-19: Real GPU-placed subagent validation and the placeholder container numbers moved to
  [docs/host/gpu-tier-scale.md](../../host/index.md#gpu-tier-scale). The validation half came back
  the same day: the dev GPU does hold the cortex, so only a placement beside a resident cortex
  needed the host.
- 2026-08-04: The `VramBudgetPlacer`'s GPU branch ran against a real placement for the first time,
  both outcomes witnessed by `brain/packages/orchestrator/tests/test_subagent_gpu_live.py`, and the
  host item closed the same day because the run kept the cortex resident. The finding is that the
  shipped placeholder numbers and not the card are why nothing was ever GPU-placed: the card holds
  both tiers with 11110 MiB free and the pair costs 14.00 GB of `nvidia-smi` total used, while the
  placeholders claim 16.8 GB for the same pair.
