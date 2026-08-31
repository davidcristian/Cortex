# The dispatch half of the rate policy

**Status:** landed 2026-07-14
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

This entry claimed the loop was "bounded by
`MAX_TOOL_STEPS`", and the ADR's risks said the same; both were false for tool spam.
`MAX_TOOL_STEPS` bounds inference **rounds**, and within one round `stream_tool_loop`
dispatched *every* call the model emitted, uncapped, on the only path reaching external
services (one round of 500 `tool_calls` was 500 dispatches; eight rounds, 4000). Now
`MAX_TOOL_DISPATCHES` (32, per loop via `ToolLoopContext.dispatch_budget`) caps the **total**
across rounds, a total rather than a per-round cap so the answer to "how many external calls
can one turn make?" is one number and not a product of two constants. Past it the call is
still handed to the dispatcher, which returns a refusal (`BUDGET_EXHAUSTED_MSG`) and audits it:
breaking out instead would strand the round's `tool_calls` without their `Role.TOOL` answers
(malformed conversation on re-inference) and produce refusals no audit record covers. The check
sits **ahead of the gate**, so hundreds of gated calls cannot become hundreds of confirmation
prompts, and **above** the `ToolStep` yield, so a refused call lights no activity chip (which
makes the chip addendum's "emission is intrinsically bounded per turn" true retroactively).
CI-gated over the fakes at 100% and mutation-proven (reverting each of the three guards
individually makes the new tests fail). Remaining behind the same seams:

## Trail

- 2026-07-14: The dispatch bound landed under the ADR's budget addendum. The index's opening
  warning cites this entry as one of the four whose own cost estimate misled planning: it and its
  ADR both claimed tool spam was bounded by `MAX_TOOL_STEPS`, and it was not, one round being able
  to dispatch unboundedly.
