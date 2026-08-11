# A delegated tool step announced and never settled

**Status:** declined 2026-08-07
**Area:** subagents
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-06 by the answer above. A subagent's `ToolStep` surfaces onto the spawning
stream as a `ToolActivity` through the progress sink, and its `StepOutcome` is dropped, so the
1:1 pairing the outcome guarantees holds for the turn's own dispatches and not for delegated
ones. That is deliberate today (the outcome exists for a consent surface over a cortex-only
built-in, and a seam field joins with a consumer or not at all), and it is worth writing down
because the moment any surface renders how a delegated step ended, the pairing becomes a claim
the progress path does not keep. The work is three lines (widen `ProgressEvent`, one arm in
`subagent_attempt.py`, one in the sink) plus deciding whether a subagent's failures are the
user's business at all, which is the real question and is not a small one.
**Declined on merits 2026-08-07**, and the pass that declined it found the claim the entry was
filed to protect already stated as a falsehood on the wire
([ADR-0029 delegated-pairing addendum](../../adr/ADR-0029-vision-screen-capture.md)). The gap itself
reproduced exactly: driving the real `converse` over a real `SpawnSubagentsTool`, a real
`SubagentRunner` and a real subagent dispatcher, with the delegate calling one tool that
succeeded and one that failed, the wire carried three `tool_activity` events and one
`tool_outcome`, the failing delegated step announced exactly like the succeeding one.
Three things the entry had wrong or did not have. The cost is **two** lines rather than three:
the sink needs no change at all, because `SeamProgressSink` is built with
`to_wire=to_server_event` and that mapper already carries a `ToolOutcome` arm for the turn's own
events, so only the `ProgressEvent` alias and one `elif` in `subagent_attempt.py` are in the way.
The consumer test is harder than "no surface renders it yet": the only reader of a `ToolOutcome`
anywhere is the overlay reducer's arm, which returns the state untouched unless the name is
`capture_screen` and `ok` is true, and `capture_screen` is a built-in that `build_builtin_tools`
feeds to `build_cortex_tools` alone, while a subagent's dispatcher comes from
`build_subagent_tools` over the MCP registry, so a delegated outcome could never carry the one
name the one reader reads. That is the `GetVolume` decline's sharper form, where nothing *could*
read it. And the reversal could not deliver the pairing anyway: `SeamProgressSink.emit` returns
without queuing when `self._credits.locked()`, while the turn's own events block on
`await self._credits.acquire()`, so a delegated outcome can be dropped while its activity got
through. Two lines cannot make 1:1 true across a lossy channel.
On the real question the entry named, a subagent's failures already reach the party who can act
on them: the runner degrades a failed subagent to an `ok=False` `SubagentResult` whose detail
`spawn.py` feeds back into the cortex's context as `[subagent i] FAILED: ...`, and the user reads
the answer shaped by it. There is no consent to surface either, since a subagent is handed the
gated-stripped subset and nothing it can call is outbound or irreversible.
**What was actually broken was the contract**, and on the body's side, which is the side that
cannot notice, a delegated activity being a byte-identical `ToolActivity`. `proto/body.proto`
said the brain emits one outcome per activity "it emitted on the turn's own stream", and a
delegated activity is emitted on exactly that stream;
`body/crates/core/src/transport/turn.rs` repeated the sentence, and `docs/modules/body-core.md`
shortened it to "one per activity", while `docs/modules/brain-orchestrator.md` had it right all
along. All three now say the pairing covers the dispatches the turn itself made and name the
unsettled delegated activity as the ordinary case. The asymmetry is pinned by
`test_a_delegated_step_reaches_the_wire_announced_and_unsettled`, which reddens under the very
`elif` the entry proposed, because the reversal is cheap enough to land as a tidy-up and would
make three published contracts wrong in one commit.
It reopens on a surface that renders how a step ended for its own sake rather than as a capture
claim (a settled or failed state on the activity chip, a delegated-work panel listing a batch's
steps), and the lossy channel reopens with it: a surface that must show an ending cannot be fed
by one that drops endings, so the honest version is a credit-blocking emit for outcomes alone or
a surface that leaves its claim where the announcement put it.

## Trail

- 2026-08-06: Opened by the capture indicator's outcome landing, which moved vision from 14 to
  13 and this area from 2 to 3. It was written up at the end of the area doc and counted on the
  index from the day it opened, but the area's own header never named it, so the move from 2 to 3
  was owed by the header rather than by the index, and the header made it the same day.
- 2026-08-07: Declined on merits, and the area header's count moved back to 2 with it, its second
  correction in two days and the second one the header rather than the index owed. The gap
  reproduced on the first run, three `tool_activity` events against one `tool_outcome` on a real
  delegating stream, and the entry was wrong about the cost, about the consumer test and about
  what the fix would buy; what the pass repaired instead is the contract in `proto/body.proto`,
  `body/crates/core/src/transport/turn.rs` and `docs/modules/body-core.md`, pinned by
  `test_a_delegated_step_reaches_the_wire_announced_and_unsettled`. Nothing downstream can tell the
  paired kind of activity from the unpaired one, so a body-side surface built on the guarantee as
  those three documents stated it would have been built on nothing. The reopening condition was
  recorded on the index's dead-until-a-consumer list, beside the `ToolActivity` wire `phase` field
  entry, which that list named as this one's sibling in the same design space.
