# The CPU row carries the CPU quota and not the memory cap

**Status:** landed 2026-09-09
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

**Landed 2026-09-09.** `Placement.reservation` returns `--cpus` at `DEFAULT_CPU_BUDGET` and
`--memory` and `--memory-swap` at `DEFAULT_MEM_BUDGET_GB`, the swap limit equal to the memory limit
because that is what disables a container's swap. Both constants are imported rather than typed, so
the row spends what the scheduler admits against. The fractional spelling was re-derived on the day:
`docker run --rm --memory 8.0g --memory-swap 8.0g alpine` reports a `memory.max` of 8,589,934,592
and a `memory.swap.max` of 0, so `f"{DEFAULT_MEM_BUDGET_GB}g"` is the whole of it and no rounding
rule is needed. Four mutations of that property each fail one of the 16 tests in
[test_switch_rows.py](../../../brain/packages/inference/tests/test_switch_rows.py), which is the
CI-side suite on the harness's rows; the table is in the
[ADR-0004 memory-cap addendum](../../adr/ADR-0004-model-lineup.md#addendum-2026-09-09-the-cpu-row-carries-the-overrides-memory-caps-as-well-as-its-quota).

The pick's own published CPU row was drawn before this shape existed and is the row with 0.77 GiB
of headroom under the cap, so redrawing it is
[R-617](617-the-picks-published-cpu-row-was-drawn-before-the-memory-cap.md).

## Trail

- 2026-09-05: opened by the close of
  [R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which applied
  the CPU half of the override's caps.
- 2026-09-08: the pick's server was run under both caps and its cgroup read. The charge is 7.23 GiB
  of 8 GiB rather than the 3.5 GiB recorded here, the trigger has fired, and the fractional suffix
  was measured to be accepted. Recorded in the
  [ADR-0004 lineup-trigger addendum](../../adr/ADR-0004-model-lineup.md#addendum-2026-09-08-three-lineup-triggers-re-read-and-a-memory-cap-already-at-90-of-its-limit).
- 2026-09-09: landed. The CPU row carries both memory caps, the swap limit equal to the memory
  limit, and four mutations of the property were each shown to fail the CI-side row suite. The
  pick's published CPU row, drawn under the quota alone, is left to
  [R-617](617-the-picks-published-cpu-row-was-drawn-before-the-memory-cap.md).
