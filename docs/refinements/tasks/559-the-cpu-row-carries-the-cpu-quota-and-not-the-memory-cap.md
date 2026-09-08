# The CPU row carries the CPU quota and not the memory cap

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

Opened 2026-09-05 by the close of
[R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which gave the
injection harness's CPU placement the compose override's CPU quota.

`Placement.reservation` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
hands the CPU row `--cpus` at the brain's `DEFAULT_CPU_BUDGET`, which is the `cpus:` line
`docker-compose.subagents.yml` sets on its server. The same service sets `mem_limit` and
`memswap_limit` at `DEFAULT_MEM_BUDGET_GB`, and the row does not.

**The trigger has fired, and the entry's own reason for leaving it was a reading of the wrong
number.** It says the pick's server held about 3.5 GiB against the 8 GiB cap, so the cap does
nothing. Measured 2026-09-08 by starting `ghcr.io/ggml-org/llama.cpp:server` on the shipped subagent
pick (gemma-4-E4B q4_0, 5,154,941,280 bytes on the mount) with the override's own argv and both its
caps, `--cpus 4.0 --memory 8g --memory-swap 8g -ngl 0 --ctx-size 8192 --parallel 2`: the model
loaded in 25.75 s, one 64-token completion returned in 22.22 s, and the container's own cgroup then
read

| `/sys/fs/cgroup` file | bytes | as GiB |
| --- | --- | --- |
| `memory.current` | 7,766,204,416 | 7.23 |
| `memory.peak` | 7,769,690,112 | 7.24 |
| `memory.max` | 8,589,934,592 | 8.00 |
| `memory.stat` `anon` | 2,579,050,496 | 2.40 |
| `memory.stat` `file` | 5,156,114,432 | 4.80 |
| `memory.stat` `inactive_file` | 5,139,607,552 | 4.79 |

so the charge the cap applies to sits at **90.4% of the limit**, with 0.77 GiB of headroom, and the
3.5 GiB figure is the kind of number `docker stats` prints: that command read `2.444GiB / 8GiB` for
the same container at the same moment, because it subtracts `inactive_file`, and the weights are
mapped from the read-only bind rather than allocated. `memory.events` read `low 0 high 0 max 0 oom 0
oom_kill 0`, so nothing was reclaimed on this run. What the cap bounds on this pick is therefore how
much of the artifact stays cached under pressure, which is a re-read from a drvfs bind when it goes,
and the margin that decides it is under a gigabyte rather than the four and a half the entry
assumed.

**A second CPU server in the same stack carries neither cap.** `llama-subagent-qwen` in
`docker-compose.subagents-roster.yml` sets no `cpus`, no `mem_limit` and no `memswap_limit`, so the
row `Placement.reservation` draws describes the default service alone. Qwen3.5-2B is in
`SUBAGENT_CANDIDATES` and is the artifact that override names, so the harness already draws a capped
CPU row for a model the stack runs uncapped. That is a separate reading from this one and is not
what this entry closes.

**What would close it.** `--memory` and `--memory-swap` at the brain's `DEFAULT_MEM_BUDGET_GB` in
the same `reservation`. The `g` suffix costs nothing to render: docker takes the fractional
spelling, `--memory 8.0g` reading back as `memory.max` of 8,589,934,592 on 2026-09-08, so
`f"{DEFAULT_MEM_BUDGET_GB}g"` is the whole of it and no rounding rule is needed.

## Trail

- 2026-09-05: opened by the close of
  [R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which applied
  the CPU half of the override's caps.
- 2026-09-08: the pick's server was run under both caps and its cgroup read. The charge is 7.23 GiB
  of 8 GiB rather than the 3.5 GiB recorded here, the trigger has fired, and the fractional suffix
  was measured to be accepted. Recorded in the
  [ADR-0004 lineup-trigger addendum](../../adr/ADR-0004-model-lineup.md#addendum-2026-09-08-three-lineup-triggers-re-read-and-a-memory-cap-already-at-90-of-its-limit).
