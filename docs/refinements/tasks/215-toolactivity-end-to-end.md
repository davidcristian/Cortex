# `ToolActivity` end to end

**Status:** done 2026-07-12
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Decided in [ADR-0009](../../adr/ADR-0009-tools-mcp.md) decision 15. The overlay half shipped first
as inline chips; the brain half followed the same day. `stream_tool_loop` yields a `ToolStep`
immediately before each audited dispatch, the engine maps it to the ephemeral domain `ToolActivity`
(never reply text, never stored), and the orchestrator maps that onto the wire event the proto has
had since Slice 2, so the already-shipped chip lit up with no overlay change.

The summary is written from the registry (the spec description's first line, capped, with the name
as a fallback) and never from model-authored arguments, since an argument echo would hand injected
content a display channel the guardrail never inspects.

**Subagent tool steps shipped on 2026-07-16**
([ADR-0010 decision 13](../../adr/ADR-0010-subagents.md)), using the same `ToolStep` to
`ToolActivity` mapping, taken off the `SubagentRunner` onto the spawning stream's new
`ProgressSink` rather than dropped. It shares one side channel with the
progress-reporting entry in [subagents.md](../index.md#subagents), since both come off the dispatch
`TurnStamp`, and the overlay renders it with no wire or reducer change.

**The dispatch rate and salience policy this entry also listed is complete.** The rate half shipped
as the priced dispatch budget, and the salience half on 2026-07-14 (ADR-0009 decisions 11 and 12),
which put a refused repeat above the `ToolStep` yield exactly as the budget did, so the chip's "a
tool is running now" meaning survives a second refusal reason.

What this left behind is the wire `phase` field, which has its own task file.

## History

- 2026-07-15: Extracted from the roadmap's deferred-refinements section, already closed on
  2026-07-12.
- 2026-07-16: The subagent tool-step sub-item closed as one side channel together with the
  progress-reporting entry in subagents.md, the two the index had flagged as one piece of work.
  Both halves of that entry's cost correction held: the engine generator really is suspended inside
  the spawn `dispatch`, and `SpawnSubagentsTool` really is built once and shared by every stream.
  The fix passes the channel per call, a `ProgressSink` port on the dispatch `TurnStamp` beside
  `budget`, so the shared tool reads the stream's sink per call and leaks no per-stream state. The
  real `RpcProgressSink` is credit-balanced rather than over-crediting like the confirmer's control
  path, since a delegating turn emits many steps.
