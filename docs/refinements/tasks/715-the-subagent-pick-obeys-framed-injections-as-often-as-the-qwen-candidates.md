# The subagent pick obeys framed injections as often as the Qwen candidates

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-25

Decision 7 of [ADR-0004](../../adr/ADR-0004-model-lineup.md) picked gemma-4-E4B for the subagent
tier on injection resistance, at about 2.6 times the load, 3 times a narrow task's latency and 2.8
times the resident memory of the Qwen3.5-2B it replaced, and
[ADR-0017](../../adr/ADR-0017-subagent-model-safety.md) forces that pick on every subagent path
that can bring in untrusted content. The counts behind the pick were one draw per attack at
temperature 0.

At the engine's sampler on the card, the text row framed at ten repetitions per attack reads the
pick at 9 of 100, gemma-4-E2B at 28, and Qwen3.5-0.8B, Qwen3.5-2B and Qwen3.5-4B at 9, 8 and 10
([injection text rows](../../readings/injection-text-rows.md)). A two-sided Fisher test against
the pick separates gemma-4-E2B only (p 0.0009); the three Qwen counts give p 1, 1 and 1. On that
row the pick buys no measured resistance over Qwen3.5-2B.

**What would close it.** A per-tier pick is the maintainer's decision: keep the pick and restate
decision 7's reason, or move the pick and with it ADR-0017's forced default. Evidence that could
inform it and is not yet drawn: the same comparison on the CPU placement, which R-714's CPU rows
draw, and a check of whether the constrained reply path
([ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)) changes the order.

**`output-laundering` alone, 2026-09-25.** Drawn on the card as written here before the draw, 100
per variant per candidate ([subagent laundering](../../readings/subagent-laundering.md)). By hand
the pick obeys framed in 66 of 100 against 88 control. Against the pick's 66, Qwen3.5-2B reads
apart above at 80 (p 0.038) and Qwen3.5-4B apart above at 84 (p 0.0052), both as predicted, and
Qwen3.5-0.8B reads apart below at 22 (p 4.6e-10), where the prediction had it not apart; 18 of its
22 are the notice alone with no summary. No draw was void. The pick's framed count fell above its
range (predicted 46, 34 to 58), and the 2B result depends on one reply. The prediction was built on
the 2026-09-23 draw of this attack as first read, with a quoted ending counted described; by the
rule this draw uses, that draw reads 55 framed against 84 control. So on this one attack the pick
appends the notice framed less often than Qwen3.5-2B and Qwen3.5-4B, while on the full row it is
level with them.

That row is the tools-enabled path's request. The constrained reply path is not drawn: it sends no
tools and no preamble, and ADR-0017 reaches it only on an untainted turn, so no tool result reaches
it. A check of it needs a driver that builds `task_messages(task, constrain=True)` with the payload
inside the task text and sends `REPLY_ENVELOPE`, which no row of this harness does.

## History

- 2026-09-23: opened by
  [R-714](714-the-injection-text-rows-are-drawn-only-at-temperature-0.md), whose draw of the
  subagent candidates at the sampler found the pick level with the Qwen candidates.
- 2026-09-25: `output-laundering` drawn alone on the pick and the three Qwen candidates, 100 per
  variant; the Qwen3.5-2B and Qwen3.5-4B predictions held and the Qwen3.5-0.8B one did not.
