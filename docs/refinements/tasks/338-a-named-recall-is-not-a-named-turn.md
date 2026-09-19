# A named recall is not a named turn

**Status:** done 2026-09-19
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`RecallPolicy.select` has a `session_id`, so the judge's two fallback warnings name the
conversation they happened in. They cannot name the recall. A session with twenty turns produces
twenty recalls, every one logging the same `session_id`, so a fallback and the trail line for the
recall it belongs to are joined only by being next to each other in the stream, which stops holding
on a busy brain and on any collector that reorders.

The gap is one level further back. `MemoryRecaller.recall(query, *, k, session_id)` takes no turn
id either, so widening the policy port alone reaches nothing: the method would have to grow one,
and `_recalled_context` in `turn_context.py`, the helper `assemble_inference_messages` calls to
recall, would have to pass `context.turn_id`, which it already has.

The plumbing is two signatures and a call. What makes it larger is that the line it would be paired
with has no turn id of its own: `LoggingRecallSink` writes `session_id` and never a turn, so a turn
on the fallback would be unmatched until `RecallAudit` grows one too. That is a third signature and
a value type, and the real decision under it is whether a recall is a fact about a turn or a fact
about a session.

## History

- 2026-08-20: Opened by the close of [R-316](316-a-rank-fallback-cannot-name-its-turn.md), which
  gave the port a session and found the turn its title asked for was two more signatures away.
  Recorded in ADR-0038 decision 15.
- 2026-09-13: Checked again, and every signature is still as described.
  `MemoryRecaller.recall(query, *, k, session_id)` takes no turn id, `RecallPolicy.select` has
  `session_id` and nothing more, `RecallAudit` has a `session_id` beside the query and the pool and
  no turn, and the judge's two warnings in `rerank_judge.py` write `session_id` into their `extra`.
  `assemble_inference_messages` still has `context.turn_id` and still logs it beside the session on
  the unavailable-memory warning. One name corrected: the sink writes `session_id` rather than
  `session`, having been renamed to the vocabulary the interface and the stores share. The decision
  the entry names is untaken, so it stays open.
- 2026-09-19: Checked again; none of its signatures moved. The only commit to the recall code since
  2026-09-13 moved per-policy tests into one shared check list. One path corrected above: the
  recall is made by `_recalled_context`, the helper `assemble_inference_messages` calls, not by
  that function itself. One entry filed since bears on the cost:
  [R-683](683-the-recall-trail-has-no-store.md) would write the recall trail to a file while the
  judge's two fallback warnings stay on the log stream, which removes even the adjacency this entry
  says a busy brain already breaks.
- 2026-09-19: Fixed as ADR-0038 decision 16. The open decision was taken: a recall is a fact about
  a turn, since `_recalled_context` recalls once per turn for that turn's query, and it keeps its
  session as the scope it read. `MemoryRecaller.recall` now requires `turn_id` and turn assembly
  passes `context.turn_id`; `RecallPolicy.select` takes an optional `turn_id` beside `session_id`,
  which the judge forwards to its fallback and writes on both warnings; `RecallAudit` has `turn_id`
  and `LoggingRecallSink` writes it. The recall policy contract now checks all five policies for
  one ranking with or without the two ids. It went in before the trail's file adapter (R-683),
  which will receive the turn on the value.
