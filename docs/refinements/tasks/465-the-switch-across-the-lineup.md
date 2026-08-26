# Two picks are not a rule about which shapes honour the thinking switch

**Status:** open, actionable
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
