# Two picks are not a rule about which shapes honour the thinking switch

**Status:** done 2026-08-28
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

`GenerationBounds.thinking=False` was measured working on a plain request and, on one pick of two,
doing nothing under a `response_format`. Both picks are gemma-4 and each cell was one run, so the
tree had two points rather than a rule. The lineup
([ADR-0004](../../adr/ADR-0004-model-lineup.md)) has more entries: the Qwen roster alternate in
`docker/docker-compose.subagents-roster.yml`, the deep tier's gemma-4-31B, and the E2B beside the
E4B. None had been asked, and the Qwen family is the one the compose comments credited with
honouring the kwarg, measured on a prompt (`17 + 25`) that invites no deliberation.

Nothing shipped depended on the answer, since every subagent server sets `--reasoning-budget 0`
anyway. Closing it means running
`brain/packages/inference/tests/test_thinking_switch_live.py` against each remaining lineup entry
on a server started with neither reasoning flag, at three or more runs per cell.

## History

- 2026-08-27: opened by the close of
  [R-458](458-the-ports-thinking-switch-is-conditional.md), as the generalisation that entry's two
  gemma-4 points could not support.
- 2026-08-28: closed. Every remaining chat entry of the lineup was asked, through the committed
  probe at five draws a cell on a server with neither reasoning flag, on llama.cpp
  `b10644-d7a207411`. Both outcomes this entry named as worth acting on happened, and neither is a
  hazard. No entry ignores the switch on the plain shape: with it sent, 0 draws of 5 deliberate
  everywhere, against 5 of 5 without it, so `TITLE_BOUNDS`, `RECAP_BOUNDS` and the reply bounds are
  safe on anything a deployment names off this lineup. Several entries honour it on both shapes, so
  the split is not a family property: every Qwen entry honours it under a schema, and gemma-4
  splits down the middle, the 12B, the 31B and the 26B-A4B honouring it where the E2B and the E4B
  do not. The E2B is the worse of that pair, deliberating through the switch on 5 draws of 5 where
  the E4B does on 4. The Qwen claim is now measured on a deliberative prompt and is true on both
  shapes; the compose comment, [ADR-0010](../../adr/ADR-0010-subagents.md) and the subagent runbook
  say so. What decides the result is the template, read off each server's `POST /apply-template`:
  an entry whose template renders the kwarg as a thought already closed honours it under a schema,
  and one that drops the block and adds nothing does not, on every entry measured. `peg-gemma4`
  serves both sides of the split, which rules the handler out. Written into the lineup table of the
  thinking-switch readings, with the selection consequence at
  [ADR-0004](../../adr/ADR-0004-model-lineup.md). Opened by it:
  [R-475](475-a-tier-can-be-asked-what-its-template-answers.md), since that prediction is one call
  a deployment could make at boot and nothing makes it.
