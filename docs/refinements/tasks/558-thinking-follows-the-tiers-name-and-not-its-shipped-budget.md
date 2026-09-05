# Thinking follows the tier's name and not its shipped budget

**Status:** open, fix when it bites
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a deployment that starts the cortex or the deep tier with `CORTEX_REASONING_BUDGET` or
`CORTEX_REASONING_BUDGET_BRAIN` at zero and wants the injection harness to draw that tier's rows as
it runs them.

Opened 2026-09-05 by the close of
[R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which made a
`Model` name its tier and read `thinking` off it.

`Model.thinking` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
is `tier != SUBAGENT_TIER`: the subagent tier is the thinking-off tier because ADR-0010 made it
one, and the cortex and deep tiers think because they ship with the unbounded budget. That is a
reading of the tier's name. The same `ModelHostConfig` the harness reads the head off carries the
answer structurally, in whether the tier's `extra` ends its trace at zero, and the harness does not
read it there.

**Why it was left.** Reading it structurally means naming the budget flag and distinguishing a zero
budget from a bounded one (`--reasoning-budget 128` is still thinking), which is the flag-naming the
harness keeps to one place. Every deployment this repo ships starts both thinking tiers unbounded,
so the nominal reading and the structural one agree everywhere a row is drawn today.

**What would close it.** `thinking` read off the tier's tail: absent, or present with a count above
zero, is thinking; present at zero is not. The test that holds each lineup to its tier would then
hold the two readings to each other.

## Trail

- 2026-09-05: opened by the close of
  [R-546](546-the-harness-takes-the-tiers-reasoning-flags-and-not-its-placement.md), which chose
  the nominal reading.
