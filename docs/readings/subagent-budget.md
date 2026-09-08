# Readings: the subagent resource budget

What the tiers the placer budgets for really cost, what an over-committed GPU load does, and what an
NPU probe from this WSL2 guest finds. Cited by [ADR-0012](../adr/ADR-0012-resource-governance.md),
decisions 12 and 14 and its consequences. VRAM figures are `nvidia-smi` total used minus an idle
baseline read immediately before the load and again after the last measurement, because the desktop
shares the card and that baseline moved by more than a GiB between sessions; per-process attribution
(`--query-compute-apps`) returns nothing under WSL2. Sizes stay absolute because a reader compares
them against their own card to decide what fits.

## The cortex reservation

**2026-08-07**, a 24463 MiB card, the cortex tier at its shipped shape (gemma-4-12B QAT q4_0,
`-ngl 99 --ctx-size 16384 --parallel 1`, its projector, a 1024-token image budget), started by the
model-host sidecar and sampled every 0.2 to 0.3 s. The two baseline readings agreed within 7 MiB.

| Phase | Above the baseline |
| --- | --- |
| idle, loaded, nothing served | 8400 to 8484 MiB |
| 13180 prompt tokens and 924 decoded, a full context | 8415 to 8460 MiB |
| one vision turn | 8441 to 8544 MiB |
| vision on a near-full context, three times | 8461 to 8573 MiB |
| idle after the images | 8463 to 8557 MiB |

Text of any length is paid for at load; the first image adds 70 to 90 MiB that stays. The peak, 8573
MiB, is 233 MiB under the 8.6 GiB reservation, a margin wider than the in-phase sampler spread (21
to 70 MiB) plus the gap between the two baseline readings. Method: start the tier through the
control API, drive each phase, sample `nvidia-smi` throughout
([llamacpp-gpu](../runbooks/llamacpp-gpu.md)).

## The subagent ask

**2026-08-08**, the same card with the cortex resident, the GPU-placed subagent tier at its shipped
shape (gemma-4-E4B QAT q4_0, `-ngl 99 --ctx-size 8192 --parallel 2`, thinking off), sampled every
0.2 s. The two baseline readings agreed within 20 MiB.

| Phase | The tier's own cost |
| --- | --- |
| idle, loaded | 3228 to 3355 MiB |
| two concurrent requests, each filling its slot | 3252 to 3325 MiB |
| four concurrent requests, three rounds | 3260 to 3390 MiB |
| the whole resident phase | up to 3410 MiB |

Serving work costs nothing extra: both slots were filled to their 4096-token halves and the reading
stayed inside the idle band's spread, and the tier has no vision path. The peak, 3410 MiB, is 174
MiB under the 3.5 GiB ask. The CPU entry's resident memory is about 2.5 GiB, the figure the
`memory_gb` ask of 3.0 is rounded up from (recorded beside it in `docker-compose.subagents.yml`).
Method: as above, driving concurrent requests through the tier's own endpoint.

## The two routes, and the budget choosing between them

**2026-08-08**, the shipped budget (14 GB cap, 8.6 reservation, 3.5 ask), a batch of two spawns of
one entry through `test_subagent_gpu_live.py`: one was GPU-placed and answered in 152 ms, its
sibling overflowed to the CPU server and answered in 13135 ms, about 86 times longer, and the GPU
tier's served-task count moved by exactly one. Under the earlier 5.5 ask both spawns overflowed and
the tier served nothing. With the GPU endpoint pointed at a closed port the run fails on three
placements rather than two, the CPU re-run firing. Method: the suite's two commands against one
stack, per [subagents-cpu](../runbooks/subagents-cpu.md).

Spawns sharing one backend object serialize on its lease: on the CPU server two concurrent spawns
took 4.8 s through two backend objects and 10.0 s through one, a ratio of 2.08 (same runbook).

## Two tiers generating at once

**2026-08-04**, the cortex and the GPU subagent tier resident together. Generating alone the cortex
decoded at 71.82 tok/s and the subagent tier at 96.96; generating at once, 50.54 and 63.50, so each
lost 30 to 35 percent of its rate. Neither left READY. Method: one completion per tier, alone and
concurrently, reading llama.cpp's `timings`.

## An over-committed load serves

**2026-07-18**, an 8 GB card (8188 MiB): a 14.4 GB GGUF, about 1.8 times the card, started with
`-ngl 99`. llama.cpp logged that it failed to fit the parameters and loaded anyway, serving
`/health` after 176.9 s with 7762 MiB of dedicated VRAM in use and the rest in shared system memory
(WDDM oversubscription under WSL2). No out-of-memory error was raised. Method: start the model with
`-ngl 99` and poll `/health` and `nvidia-smi`.

## The NPU from a container

**2026-08-20 and 2026-09-08**, the WSL2 guest on an Intel Core Ultra 9 275HX laptop.

- In a `python:3.12-slim` container given `/dev/dxg` and `/usr/lib/wsl`, OpenVINO 2026.3.1 loads
  its NPU plugin, `Core().available_devices` reads `['CPU']` and
  `Core().get_property("NPU", "AVAILABLE_DEVICES")` reads `[]`.
- The guest has `/dev/dxg` and no `/dev/accel`, and its kernel is built with
  `# CONFIG_DRM_ACCEL is not set`, which the `intel_vpu` driver depends on.
- `D3DKMTEnumAdapters2` through `libdxcore.so` reports three adapters required and returns two, the
  discrete and the integrated GPU. The third opens by LUID and reports itself render, compute only
  and paravirtualized, at host PCI address `00:0B.0`, where this CPU generation's NPU sits; that it
  is the NPU is inferred from the address, the type and the staged driver packages, since the guest
  cannot read Windows device state.
- Of the 1,038 Windows driver packages WSL maps into `/usr/lib/wsl/drivers`, three ship Linux user
  mode libraries (Intel graphics twice, NVIDIA once); Intel's NPU packages ship Windows DLLs only.

Method: the OpenVINO calls in a container, `ls /dev`, `/proc/config.gz`, and the DXCore calls from
the guest.
