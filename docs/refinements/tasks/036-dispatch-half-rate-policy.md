# The dispatch half of the rate policy

**Status:** done 2026-07-14
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

This entry and its ADR both claimed the tool loop was bounded by `MAX_TOOL_STEPS`, and both were
wrong about tool spam. `MAX_TOOL_STEPS` bounds inference rounds, and within one round
`stream_tool_loop` dispatched every call the model emitted, uncapped, on the only path that
reaches external services: one round of 500 `tool_calls` was 500 dispatches, and eight rounds
4000.

`MAX_TOOL_DISPATCHES` (32, per loop via `ToolLoopContext.dispatch_budget`) now caps the total
across rounds. A total rather than a per-round cap, so the answer to "how many external calls can
one turn make?" is one number and not the product of two constants. Past the cap the call is still
handed to the dispatcher, which returns a refusal (`BUDGET_EXHAUSTED_MSG`) and records it in the
audit: breaking out instead would leave the round's `tool_calls` without their `Role.TOOL`
answers, which is a malformed conversation on re-inference, and would produce refusals no audit
record covers. The check sits ahead of the confirmation step, so hundreds of calls needing
approval cannot become hundreds of prompts, and above the `ToolStep` yield, so a refused call
lights no activity chip.

Covered at 100% over the fakes, and each of the three guards was reverted individually to check
that the new tests fail.

## History

- 2026-07-14: The dispatch bound was added as ADR-0009 decision 11. This is one of the entries
  whose own cost estimate misled planning: it and its ADR both claimed tool spam was bounded by
  `MAX_TOOL_STEPS`, and one round could dispatch without limit.
