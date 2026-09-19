# Nothing checks that a cap sized on the answer runs on a tier whose trace is bounded

**Status:** declined 2026-09-12
**Area:** inference
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

The rule this repo keeps is that a `max_tokens` sized on the wanted answer is only safe when the
reasoning trace is bounded, because a reasoning model spends its budget thinking first. Three
shipped bounds pair a cap with `thinking=False` and treated that as the bound: `RECAP_BOUNDS`,
`TITLE_BOUNDS` and `rank_bounds(k)`. That switch is a request the deployment may not honour, so the
rule's precondition can be false at runtime while every check passes.

Since 2026-08-29 all three also send `trace_tokens=0`, which llama.cpp reads off the request body
as a sampler rather than passing to a chat template. Measured at a hundred draws a cell on the
shipped subagent pick, on each of the two builds this host can start, the switch alone left 85 and
86 draws of 100 deliberating into an empty capped reply, and the switch with the zero left 0 of
100. Whether an engine reads the key is asked once at boot (`CORTEX_INFERENCE_TRACE_LEVER`) and
logged.

A check was not built because it would need a fact the core does not have: whether a tier's trace is
bounded by its argv lives in the model host's config and in two compose files, and the core reaches
inference through a port that says nothing about how the server was started.

## History

- 2026-08-27: opened by the close of
  [R-458](458-the-ports-thinking-switch-is-conditional.md), which made the ignored switch visible at
  runtime through `drain_text` and left the pairing possible to write.
- 2026-09-12: declined, and the body is corrected twice. It said four shipped bounds pair a cap with
  the switch; there were three on the day it was written and there are three now, the fourth cap in
  the tree being `SubagentAttempt`'s, which names no switch and relies on its tier's flags by
  decision. And the premise moved: all three have sent `trace_tokens=0` since 2026-08-29, so on a
  deployment whose engine reads the key the precondition is met. Of the three candidate fixes, a
  port capability saying the trace is bounded is declined because llama.cpp offers no way to ask,
  so the value would be a deployment's claim about itself; and the two that would compare a bound
  with a tier's budget flag are declined because the value they would compare is the cortex tier's
  budget default, which is unbounded deliberately, since the same tier serves the user's reply and
  its trace is the thinking status the overlay renders (ADR-0020). What survives is narrower:
  nothing checks that a fourth side call sends the same zero, which is
  [R-650](650-nothing-holds-a-side-call-to-the-request-level-zero.md).
