# The CPU row carries the CPU quota and not the memory cap

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a subagent candidate whose resident size on the CPU approaches the override's
`CORTEX_SUBAGENTS_MEM_BUDGET_GB`, or a CPU row whose reading a reader wants to attribute to the
container's memory rather than to the model.

Opened 2026-09-05 by the close of
[R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which gave the
injection harness's CPU placement the compose override's CPU quota.

`Placement.reservation` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
hands the CPU row `--cpus` at the brain's `DEFAULT_CPU_BUDGET`, which is the `cpus:` line
`docker-compose.subagents.yml` sets on its server. The same service sets `mem_limit` and
`memswap_limit` at `DEFAULT_MEM_BUDGET_GB`, and the row does not. The quota was added because it
changes what the row costs, the uncapped server decoding at 0.8 tokens a second and the row taking
819 s against about 0.4 and 1837 s under it; the memory cap changes nothing until a model reaches it, and the pick's server held about
3.5 GiB against the 8 GiB cap.

**Why it was left.** A memory cap a process stays under is a cap that does nothing, and applying it
would spell the compose file's `g` suffix rule a third time. The cost is one line and the reading
that would need it has not been asked for.

**What would close it.** `--memory` and `--memory-swap` at the brain's `DEFAULT_MEM_BUDGET_GB`,
rendered the way the compose file renders them, in the same `reservation`.

## Trail

- 2026-09-05: opened by the close of
  [R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which applied
  the CPU half of the override's caps.
