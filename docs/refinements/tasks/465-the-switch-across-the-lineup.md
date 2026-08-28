# Two picks are not a rule about which shapes honour the thinking switch

**Status:** landed 2026-08-28
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-27 by the close of
[R-458](458-the-ports-thinking-switch-is-conditional.md), which measured two picks and generalised
about neither.

`GenerationBounds.thinking=False` was measured holding on a plain request and, on one pick of two,
doing nothing under a `response_format`. Both picks are gemma-4, one run per cell, so what the tree
now holds is two points and a probe rather than a rule. The lineup ([ADR-0004](../../adr/ADR-0004-model-lineup.md))
has more entries than that: the Qwen roster alternate `docker/docker-compose.subagents-roster.yml`
ships, the deep tier's gemma-4-31B, and the E2B beside the E4B. None has been asked the question,
and the Qwen family is the one whose template the compose comments have always credited with
honouring the kwarg, measured on a prompt (`17 + 25`) that invites no deliberation and therefore
proves nothing about it either.

**Why it was left.** Nothing shipped depends on the answer. Every subagent server carries
`--reasoning-budget 0` regardless, and the cortex tier was re-measured on all four of its own bound
shapes. Running the roster alternate and the deep tier is a stack bring-up per pick for a reading
that changes no code unless it is surprising.

**What would close it.** Point `brain/packages/inference/tests/test_thinking_switch_live.py` at each
remaining lineup entry with a server started carrying neither reasoning flag, and record the verdict
per shape in the ADR-0005 switch-is-advisory addendum's table. Two outcomes are worth acting on: a
pick that ignores the switch on the **plain** shape too would make `TITLE_BOUNDS`, `RECAP_BOUNDS`
and the reply bounds unsafe on it, and a pick that honours it on **both** shapes would say the
split is not a family property. Three or more runs per cell on any pick that lands in between, since
the current reading is one draw and the entry it came from was closed the first time by exactly that
kind of single draw.

## Trail

- 2026-08-27: opened by the close of
  [R-458](458-the-ports-thinking-switch-is-conditional.md), as the generalisation that entry's two
  gemma-4 points could not carry.
- 2026-08-28: Landed. Every remaining chat entry of the lineup was asked, through the committed
  probe at five draws a cell on a server carrying neither reasoning flag, on llama.cpp
  `b10644-d7a207411`. **Both of the outcomes this entry named as worth acting on fired, and neither
  is a hazard.** No entry ignores the switch on the plain shape: with it sent, 0 draws of 5
  deliberate everywhere, against 5 of 5 without it, so `TITLE_BOUNDS`, `RECAP_BOUNDS` and the reply
  bounds are safe on anything a deployment names off this lineup. And several entries honour it on
  **both** shapes, so the split is not a family property: every Qwen entry holds under a schema, and
  gemma-4 splits down the middle of its own, the 12B, the 31B and the 26B-A4B holding where the E2B
  and the E4B do not. The E2B is the worse of that pair, deliberating through the switch on 5 draws
  of 5 where the E4B does on 4.
  The Qwen claim this entry singled out, credited to a `17 + 25` that proved nothing, is measured on
  a deliberative prompt now and is true on both shapes; the compose comment that carried it,
  [ADR-0010](../../adr/ADR-0010-subagents.md) and the subagent runbook say so.
  **What decides a verdict is neither the family nor the chat handler but the template**, read off
  each server's own `POST /apply-template`: an entry whose template answers the kwarg with a thought
  already closed holds under a schema, and one that drops the block and adds nothing does not, on
  every entry measured. `peg-gemma4` serves both sides of the split, which is what rules the handler
  out. Written into the ADR-0005 switch-is-advisory addendum as its lineup section, with the
  selection consequence at [ADR-0004](../../adr/ADR-0004-model-lineup.md).
  Opened by it: [R-475](475-a-tier-can-be-asked-what-its-template-answers.md), since that predictor
  is one call a deployment could make at boot and nothing makes it.
