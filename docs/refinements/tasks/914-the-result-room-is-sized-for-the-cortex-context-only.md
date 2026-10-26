# The result room is sized for the cortex context only

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-10-26

`RESULT_ROOM_CHARS` (`tool_cut.py`) is 6,000 characters, 3,640 tokens at a pasted log's 1.65
characters a token. Decision 20 of ADR-0009 derives it from the cortex's context of 16,384 tokens,
a full history window and the fixed prompt. Every `stream_tool_loop` builds the same room, whatever
model it runs on.

A subagent with tools runs that loop too (`subagent_attempt.py`, `SubagentRunner(tools=...)` in
`subagent_builders.py`), on a server started with `CORTEX_SUBAGENT_CTX_SIZE`, 8,192 tokens by
default. There the room is 44% of the context, beside the task's own messages, which can quote
text, and the reply's generation bound. The deep model's server takes `CORTEX_CTX_SIZE_BRAIN`, so a
smaller value there shrinks its margin the same way, and a larger one leaves room unused.

Not shown yet: no subagent request has been seen to pass its context because of the room. Before
the room, each result was cut to 6,000 characters alone, so a subagent could already hold more.

## What to do

1. Measure on the GPU stack: a subagent task with the file tools that reads one large log, then
   several in one round, at the default context. Write the rows and what counts as an overflow in
   a readings record before the run.
2. If a row overflows, size the room per loop from the serving tier's context (a `ToolLoopContext`
   field set where each loop is built, as `results_spent` is), keep the cortex's value, and test
   each tier's room with a fake.

## History

- 2026-10-26: filed from the audit of the shared result room.
