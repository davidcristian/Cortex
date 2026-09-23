# The subagent pick obeys framed injections as often as the Qwen candidates

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-23

Decision 7 of [ADR-0004](../../adr/ADR-0004-model-lineup.md) picked gemma-4-E4B for the subagent
tier on injection resistance, at about 2.6 times the load, 3 times a narrow task's latency and 2.8
times the resident memory of the Qwen3.5-2B it replaced, and
[ADR-0017](../../adr/ADR-0017-subagent-model-safety.md) forces that pick on every subagent path
that can bring in untrusted content. The counts behind the pick were one draw per attack at
temperature 0.

At the engine's sampler on the card, the text row framed at ten repetitions per attack reads the
pick at 8 of 100, gemma-4-E2B at 28, and Qwen3.5-0.8B, Qwen3.5-2B and Qwen3.5-4B at 9, 7 and 10
([injection text rows](../../readings/injection-text-rows.md)). A two-sided Fisher test against
the pick separates gemma-4-E2B only (p 0.0004); the three Qwen counts give p 1, 1 and 0.81. On that
row the pick buys no measured resistance over Qwen3.5-2B.

**What would close it.** A per-tier pick is the maintainer's decision: keep the pick and restate
decision 7's reason, or move the pick and with it ADR-0017's forced default. Evidence that could
inform it and is not yet drawn: the same comparison on the CPU placement, a deeper draw on
`output-laundering`, which the pick obeys framed in 46 of 100 and the Qwen candidates in 6 to 8 of
10, and a check of whether
the constrained reply path ([ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)) or the
tools-enabled path changes the order.

## History

- 2026-09-23: opened by
  [R-714](714-the-injection-text-rows-are-drawn-only-at-temperature-0.md), whose draw of the
  subagent candidates at the sampler found the pick level with the Qwen candidates.
