# A delegated tool step announced and never settled

**Status:** declined 2026-08-07
**Area:** subagents
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

A subagent's `ToolStep` reaches the spawning stream as a `ToolActivity` through the progress sink,
and its `StepOutcome` is dropped. So the one-outcome-per-activity pairing holds for the turn's own
dispatches and not for delegated ones.

**Declined on merits 2026-08-07** ([ADR-0029 decision
18](../../adr/ADR-0029-vision-screen-capture.md)). The gap reproduced on the first run: driving
the real `converse` over a real `SpawnSubagentsTool`, a real `SubagentRunner` and a real subagent
dispatcher, with the delegate calling one tool that succeeded and one that failed, the wire
had three `tool_activity` events and one `tool_outcome`, the failing delegated step announced
exactly like the succeeding one.

Three things the entry had wrong. The cost is two lines rather than three: `RpcProgressSink` is
built with `to_wire=to_server_event`, and that mapper already handles a `ToolOutcome`, so only the
`ProgressEvent` alias and one `elif` in `subagent_attempt.py` are in the way. The consumer test is
stronger than "no surface renders it yet": the only reader of a `ToolOutcome` anywhere is the
overlay reducer, which returns the state untouched unless the name is `capture_screen` and `ok` is
true, and `capture_screen` is a built-in that `build_builtin_tools` feeds to `build_cortex_tools`
alone, while a subagent's dispatcher comes from `build_subagent_tools` over the MCP registry, so a
delegated outcome could never have the one name the one reader reads. And the change could not
deliver the pairing anyway: `RpcProgressSink.emit` returns without queuing when
`self._credits.locked()`, while the turn's own events block on
`await self._credits.acquire()`, so a delegated outcome can be dropped while its activity got
through.

A subagent's failures already reach the party who can act on them: the runner degrades a failed
subagent to an `ok=False` `SubagentResult` whose detail `spawn.py` feeds back into the cortex's
context as `[subagent i] FAILED: ...`, and the user reads the answer shaped by it. There is no
consent to show either, since a subagent is handed the subset with confirmation-only tools removed and
nothing it can call is outbound or irreversible.

**What was actually wrong was the written contract**, on the body's side, which cannot tell the
two kinds of activity apart. `proto/body.proto` said the brain emits one outcome per activity "it
emitted on the turn's own stream", and a delegated activity is emitted on exactly that stream;
`body/crates/core/src/transport/turn.rs` repeated the sentence and `docs/modules/body-core.md`
shortened it to "one per activity", while `docs/modules/brain-orchestrator.md` had it right. All
three now say the pairing covers the dispatches the turn itself made, and name the unsettled
delegated activity as the ordinary case. `test_a_delegated_step_reaches_the_wire_announced_and_unsettled`
asserts it, and fails under the very `elif` the entry proposed, because that change is cheap
enough to make as a tidy-up and would make three published contracts wrong in one commit.

It reopens on a surface that shows how a step ended for its own sake, such as a settled or failed
state on the activity chip or a delegated-work panel listing a batch's steps. The lossy channel
reopens with it: a surface that must show an ending cannot be fed by one that drops endings, so
the accurate version is a credit-blocking emit for outcomes alone, or a surface that leaves its
claim where the announcement put it.

## History

- 2026-08-06: Opened by the capture indicator's outcome work, which moved vision from 14 to 13 and
  this area from 2 to 3. It was counted on the index from the day it opened, but the area's own
  header never named it until the same day.
- 2026-08-07: Declined on merits, and the area header's count moved back to 2. The reopening
  condition was recorded on the index's waiting-for-a-consumer list, beside the `ToolActivity`
  wire `phase` field entry, which that list named as this one's sibling.
