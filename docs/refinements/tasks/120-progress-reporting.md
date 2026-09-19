# Subagent progress reporting over the `Converse` status stream

**Status:** done 2026-07-16
**Area:** subagents
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)

v1 delegation is synchronous inside the cortex turn, so nothing reached the overlay while
subagents ran. Two facts shaped the fix and were both confirmed against the code first. While a
spawn runs, the engine generator is suspended inside `await dispatcher.dispatch(...)` in
`tool_loop.py`, so it cannot yield an event; progress needs a side channel writing to the
`Converse` queue directly. And `SpawnSubagentsTool` is built once in `subagent_builders.py` and
shared by every turn, so it cannot hold one turn's stream.

**Shipped 2026-07-16** ([ADR-0010 decision 13](../../adr/ADR-0010-subagents.md)), passing the
channel per call rather than making the tool per-stream. A pure-core `ProgressSink` port in
`progress.py` travels on the dispatch `TurnStamp` beside `budget`, as a live handle with
`compare=False`, so the one shared `SpawnSubagentsTool` reads the stream's sink off
`call.stamp.progress` per call and keeps no per-stream state. A test routes two sinks through one
tool to show nothing leaks between them.

It serves this entry and the tool-step chip entry at once: `SpawnSubagentsTool` emits a
`StatusUpdate(state="delegating", "delegating N subtasks")` for the batch's size, and
`SubagentRunner` maps each subagent's `ToolStep` onto the sink as a registry-authored
`ToolActivity`. The real adapter `SeamProgressSink` puts onto the stream's own output queue and
takes a credit only when one is free, dropping otherwise, rather than using the confirmer's
over-crediting path, since a delegating turn emits many steps. Order is preserved because the
turn task is suspended in `dispatch` and puts nothing itself meanwhile.

Nothing model-authored or untrusted travels on the sink, only the count and the matched
`ToolSpec`'s fields, so a tainted subagent's progress needs no guardrail pass. No proto change was
needed, since the overlay already renders `ToolActivity` and `StatusUpdate`. The wording says
"delegating" rather than "running in parallel", which matches the measured same-model
serialization (ADR-0012).

## History

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section into this area, among the
  Slice 7 subagent-runner deferrals recorded at ADR-0010.
- 2026-07-16: Shipped as one side channel shared with the subagent tool-step chip entry in
  [email-confirmer.md](../index.md#email-confirmer), which the index had flagged as one piece of
  work, so both areas' counts moved together (subagents 2 to 1, email and confirmer 7 to 6).
