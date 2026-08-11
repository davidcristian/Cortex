# Subagent progress reporting over the `Converse` status stream

**Status:** landed 2026-07-16
**Area:** subagents
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)

v1 delegation is synchronous
within the cortex turn; surfacing per-subagent progress to the overlay is a later refinement. See
ADR-0010 risks. **Cost correction:** this is not a progress-sink parameter. While a spawn runs,
the engine generator is suspended inside `await dispatcher.dispatch(...)` in `tool_loop.py`, so
it cannot yield an event; progress needs a side channel writing to the `Converse` queue directly.
And `SpawnSubagentsTool` is built **once** in `subagent_builders.py` and shared by every turn, so
it must become per-stream (or carry the stream's channel per call) before it can address one
turn's overlay.
**Landed 2026-07-16 ([ADR-0010 progress addendum](../../adr/ADR-0010-subagents.md)), as the
carry-the-channel-per-call option.** Both halves of the cost correction were confirmed against
the code before building: the suspended generator (the spawn `dispatch` is awaited in
`tool_loop.py`, so `handle_turn` cannot yield while subagents run) and the shared singleton
(`build_subagents` runs once in `wiring.run_from_env` and its `spawn_tool` goes into `builtins`,
built once and reused by every per-stream `make_engine`). A new pure-core `ProgressSink` port
(`progress.py`, port-free so `tools.py` may depend on it) rides the dispatch `TurnStamp` beside
`budget` (a live handle, `compare=False`), so the one shared `SpawnSubagentsTool` reads the
stream's sink off `call.stamp.progress` per call and holds no per-stream state to leak, which is
the "carry the channel per call" alternative the entry named (a per-stream tool was the other).
It serves **both** this entry and the tool-step surfacing entry: `SpawnSubagentsTool` emits a
`StatusUpdate(state="delegating", "delegating N subtasks")` for the batch's scale and the
`SubagentRunner` maps each subagent's `ToolStep` onto the sink as a registry-authored
`ToolActivity`. The real adapter `SeamProgressSink` puts onto the stream's own output queue
**credit-balanced** (takes a credit only when free, drops otherwise), not the confirmer's
over-crediting control path, since a delegating turn emits many steps; ordering is preserved
because the turn task is suspended in `dispatch` and puts nothing itself meanwhile. Nothing model-
or untrusted-authored ever rides the sink (only the count and the matched `ToolSpec`'s fields),
so a tainted subagent's progress needs no guardrail pass, the `ToolActivity` argument reused. **No
proto change**: the overlay already renders `ToolActivity`/`StatusUpdate`, so the wire and the
overlay reducer were untouched. The parallelism claim was avoided in the wording ("delegating",
not "running in parallel"), honest to the measured same-model serialization (ADR-0012).

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section into this area doc, kept
  verbatim, among the Slice 7 subagent-runner deferrals recorded at ADR-0010.
- 2026-07-16: Landed as one side channel shared with the subagent tool-step chip surfacing entry
  in [email-confirmer.md](../index.md#email-confirmer), which the index had flagged as one piece of work,
  so both areas' counts moved together (subagents 2 to 1, email and confirmer 7 to 6). The fix
  took the carry-the-channel-per-call option of the two the entry named rather than a per-stream
  tool, with a test routing two sinks through one tool to prove no per-stream state leaks, and it
  needed no proto change; the wording avoids a parallelism claim the same-day admission-wall
  measurement showed the wiring does not deliver.
