# Readings: the subagent resource budget

What the tiers the placer budgets for really cost, what an over-committed GPU load does, and what an
NPU probe from this WSL2 guest finds. Cited by [ADR-0012](../adr/ADR-0012-resource-governance.md),
decisions 12 and 14 and its consequences, and by [ADR-0018](../adr/ADR-0018-heterogeneous-subagents.md)
decision 12. VRAM figures are `nvidia-smi` total used minus an idle
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
MiB, is from before the tier had a drafter. The reservation is 8.9 GiB, 246 MiB over the 8,868 MiB
peak with the drafter ([tier drafters](tier-drafters.md)), a margin wider than the in-phase sampler
spread (21 to 70 MiB) plus the gap between the two baseline readings. Method: start the tier through the
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

**2026-08-08**, a budget of a 14 GB cap, an 8.6 reservation and a 3.5 ask, a batch of two spawns of
one entry through `test_subagent_gpu_live.py`: one was GPU-placed and answered in 152 ms, its
sibling overflowed to the CPU server and answered in 13135 ms, about 86 times longer, and the GPU
tier's served-task count moved by exactly one. Under the earlier 5.5 ask both spawns overflowed and
the tier served nothing. With the GPU endpoint pointed at a closed port the run fails on three
placements rather than two, the CPU re-run firing. Method: the suite's two commands against one
stack, per [subagents-cpu](../runbooks/subagents-cpu.md).

Spawns that share one slot serialize on its lease: on the CPU server two concurrent spawns took
4.8 s through two leases and 10.0 s through one, a ratio of 2.08 (same runbook).

## Two slots against two servers

**2026-11-16 and 2026-11-17**, gemma-4-E4B with its multi-token-prediction drafter at draft
length 3, `llama-server` build b12375, on the 24 GB card. Two subagents of the one model were run
as two slots of one server and as two servers of one slot.

| shape | context per slot | memory | read |
| --- | --- | --- | --- |
| one server, two slots, drafter | 8K | 3,609 MiB | at load |
| one server, two slots, no drafter | 8K | 3,402 MiB | at load |
| one server, one slot, drafter | 8K | about 3,600 MiB | at its peak |
| two servers, one slot each, drafter | 8K | 3,387 and 3,389 MiB | at load, beside the cortex |

With both slots of the one server busy, each wrote at 0.68 and 0.67 of the rate one slot wrote
alone. At the peak the two servers were counted as about 7,250 MiB and the one two-slot server as
about 3,850 MiB: a second server costs the whole footprint again, about 3,400 MiB, where the
second slot is inside the first server's.

Loaded beside the gemma-4-12B cortex with every context filled and every server busy, both shapes
fit a model budget of 18,177 MiB at the peak, which is the card's 24,463 MiB less 4,750 MiB counted
for the desktop's apps and 1,536 MiB kept free: 16,659 MiB with one two-slot server and a 256K cortex
context, 17,678 MiB with two servers and a 160K cortex context. The larger footprint of two servers
was paid from the cortex's context. Method: the baseline driver, raw rows in
`measurements/model-baseline-2026-11-16/bench/slots.jsonl` and `bench/together.jsonl`.

**2026-11-18**, the same model started with no drafter, on build
b12375. The model host started each shape from the compose settings, and one batch of two spawns
went through the brain's own subagent wiring with room in the VRAM budget for both. The idle
baseline was 2,359 to 2,374 MiB, read before each load and after each teardown.

| shape | settings | context per slot | loaded | peak while the batch ran |
| --- | --- | --- | --- | --- |
| one server of one slot | `CORTEX_SUBAGENTS_GPU_SERVERS=1` | 8K | 3,328 MiB | 3,338 MiB |
| two servers of one slot | `CORTEX_SUBAGENTS_GPU_SERVERS=2` | 8K | 6,387 MiB | 6,407 MiB |
| one server of two slots | one server, `CORTEX_SUBAGENTS_GPU_PARALLEL=2`, a 16K pool | 8K | 3,508 MiB | 3,520 MiB |

With one server of one slot the host answered 404 for `subagent-gpu-2`, and the two spawns ran one after
the other: no sample of the server's `GET /slots` showed more than one slot busy. With two servers
both were busy in 115 of 117 samples and neither had more than one slot busy, so the two spawns were
leased to different servers. With two slots the one server had both busy. Method: `shape.sh` and
`drive.py` in `~/.cache/cortex-run/2026-11-18/`, compose project `cortexn24`, logs in `logs/` there.

**2026-11-18**, the shipped defaults with only the subagent file named and no server drafting, on
build b12375 (the same stack with its drafters is in [tier drafters](tier-drafters.md)): the
gemma-4-12B cortex at 16K, text only, beside two gemma-4-E4B servers of one 8K slot. The host
listed `cortex`, `subagent-gpu` and `subagent-gpu-2` and answered 404 for `subagent-gpu-3`. On the
budget of that day (16 GB cap, 8.6 reservation, 3.5 ask) `placed_at_once` put a spawn on each
of the 2 GPU slots. One batch of two spawns ran while the cortex wrote 500 tokens: both subagent
servers were busy in 111 of 311 samples, the cortex was busy in each of those, and no server had
more than one slot busy. One of the two spawns ended at the driver's 400-token limit. Above an idle
baseline of 2,394 MiB the three servers held 13,686 MiB loaded and 13,712 MiB at the peak, when the
card read 16,106 MiB of its 24,463 in use. That peak is under the 15,974 MiB the placer charges
for the three and the 16,384 MiB of the cap. Method: `shape2.sh` and `drive2.py` in the same
directory, log `logs/newdefault.txt`.

## A CPU server at two threads against four

**2026-11-18**, gemma-4-E4B on the CPU image, build b10680, `-ngl 0`, the compose service's flags
with `--ctx-size 8192 --parallel 1`, each row a server of its own on `--cpuset-cpus 12-15`. The
rate is the median of three seeds of a 20-token prompt with 256 tokens written, as a ratio of the
first row. Memory is the cgroup's own count, which charges the mapped model file beside the
anonymous memory; the last two columns were read after the last request.

| row | caps | wrote | cgroup peak | anonymous | model file resident |
| --- | --- | --- | --- | --- | --- |
| four threads | `--cpus 4.0`, 8g | 1.0 | 6,909 MiB | 2,799 MiB | 4,083 MiB |
| two threads | `--cpus 2.0`, 4g | 0.59 | 4,096 MiB, the cap | 2,799 MiB | 1,269 MiB |
| four threads, slot filled | `--cpus 4.0`, 4g | 0.90, one seed | 4,096 MiB, the cap | 2,909 MiB | 1,156 MiB |

The third row read a prompt of 7,340 tokens first and then drew one seed of the short prompt. A
server of two threads wrote at 0.59 of the rate of one of four, and that row also ran at its memory
cap, which cost a tenth on the one seed of the third row. Two busy slots of one four-thread server
each write at 0.69 to 0.75 of one slot alone ([model lineup](model-lineup.md), 2026-09-11), so on
these rows a CPU server per subagent at half the threads is slower for two subagents and for one.
No server holds its weights under 4 GiB: under that cap the kernel kept under a third of the file
in memory, and nothing was killed. The cgroup was throttled in
292 of 797, 250 of 1,225 and 428 of 1,555 periods. Method: `cpudraw.sh` and `cpudrive.py` in
`~/.cache/cortex-run/2026-11-18/`, logs `logs/cpu-t4.txt`, `cpu-t2.txt` and `cpu-fill.txt`.

**2026-11-18**, two subagents at once in both shapes, on the same model, image, build and prompt.
The one server ran on `--cpuset-cpus 12-15` with `--cpus 4.0 --threads 4 --parallel 2` under 8g,
where the engine gives each slot 4,096 of the 8,192 tokens. The two servers ran on `12-13` and
`14-15`, each with `--cpus 2.0 --threads 2 --parallel 1`. A rate is a ratio of the median of one
request alone on the two-slot server. A busy cell is the range of six requests, two at once in
three rounds.

| row | memory cap | one alone | each of two at once | cgroup peak |
| --- | --- | --- | --- | --- |
| one server of two slots | 8g | 1.0 | 0.67 to 0.69 | 6,960 MiB |
| two servers of one slot | none | 0.63 | 0.56 to 0.57 | 4,857 and 4,807 MiB |
| two servers of one slot | 4g each | not drawn | 0.55 to 0.56 | 4,096 MiB each, the cap |

Each busy server wrote below each busy slot, and the two servers together wrote at 0.83 of the
two slots together. A server's own two cores did not keep its rate: it fell from 0.63 to 0.56
when the other server was busy. The kernel charges a page of the mapped model file to the cgroup
that reads it first, so the two uncapped servers held 2,035 and 1,986 MiB of the file, about the
file once between them, beside 2,799 and 2,802 MiB of anonymous memory. Together they peaked at
9,665 MiB against 6,960 MiB for the one server. Under 4 GiB each the two kept 1,272 and
1,275 MiB of the file and the rate fell by 0.01. Method: `cpudraw7.sh` and `cpudrive7.py` in the
same directory, logs `logs/cpu2-slots.txt`, `cpu2-servers.txt` and `cpu2-servers4g.txt`.

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
