# `ToolActivity` end to end

**Status:** landed 2026-07-12
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

`ToolActivity` end to end is recorded at the [ADR-0009 chip
addendum](../../adr/ADR-0009-tools-mcp.md).
The overlay half landed first (the Slice-8 gap closure's inline chips); the brain half followed
the same day: `stream_tool_loop` yields a `ToolStep` immediately before each audited dispatch,
the engine maps it to the ephemeral domain `ToolActivity` (the ADR-0020 ephemerality
precedent: never reply text, never persisted; its registry-authored fields need no
guardrail pass; the subagent runner drops it), and the orchestrator maps
that onto the wire event the proto carried since Slice 2, so the already-shipped chip lit up
with no overlay change. The summary is registry-authored (spec description first line, capped,
name fallback), never model-authored arguments (an argument echo would hand injected content a
display channel the ADR-0015 guardrail never inspects). What this landing left behind the same
seams is the wire `phase` field, which has its own task file.
**Subagent tool-step surfacing landed 2026-07-16 ([ADR-0010 progress addendum](../../adr/ADR-0010-subagents.md)),
the same `ToolStep`-to-`ToolActivity` mapping this chip already uses, now off the `SubagentRunner`
onto the spawning stream's new `ProgressSink` rather than dropped.** It shares the one side channel
with the ADR-0010 progress-reporting entry (both surface off the dispatch `TurnStamp`, full record
in [subagents.md](../index.md#subagents)): the subagent's step is the same registry-authored chip, so the
overlay renders it with **no wire or reducer change** (the deferral's "the subagent runner drops
it" note is now "maps it onto the sink when it has one"). The
**dispatch rate/salience policy** this entry also listed is now complete: its rate half landed
as the budget and cost addenda, and its salience half 2026-07-14 (the ADR-0009 tools-block
entry in [tools-mcp.md](../index.md#tools-mcp)), which put a refused repeat above the `ToolStep` yield exactly as the budget did,
so the chip's "a tool is running now" reading survived a second refusal reason.

## Trail

- 2026-07-15: extracted from the ROADMAP's deferred-refinements section with the entry kept
  verbatim, already carrying its 2026-07-12 landing.
- 2026-07-16: the subagent tool-step surfacing sub-item landed as one side channel together with
  the ADR-0010 progress-reporting entry in subagents.md, the two the index had flagged as one
  piece of work, decrementing both counts (subagents 2 to 1, email and confirmer 7 to 6). Both
  halves of that entry's cost correction held against the code: the engine generator really is
  suspended inside the spawn `dispatch`, and `SpawnSubagentsTool` really is built once and shared
  by every stream. The fix carried the channel per call, a `ProgressSink` port riding the dispatch
  `TurnStamp` beside `budget`, so the shared tool reads the stream's sink per call and leaks no
  per-stream state; it needed no proto change, and the real `SeamProgressSink` is credit-balanced
  rather than the confirmer's over-crediting control path, since a delegating turn emits many
  steps.
