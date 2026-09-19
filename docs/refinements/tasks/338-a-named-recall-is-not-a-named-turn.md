# A named recall is not a named turn

**Status:** open, a seam or port change comes first
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)
**Verified:** 2026-09-19

`RecallPolicy.select` now carries a `session_id`, so the judge's two fallback warnings name the
conversation they happened in. They still cannot name the recall. A session with twenty turns
produces twenty recalls, every one of them logging the same `session_id`, so a fallback and the
trail line for the recall it belongs to are joined only by adjacency in the stream, which is
exactly what stops holding on a busy brain and on any collector that reorders.

The gap is one level further back than the one just closed. `MemoryRecaller.recall(query, *, k,
session_id)` takes no turn id either, so widening the policy port alone reaches nothing: the method
would have to grow one, and `_recalled_context` in `turn_context.py`, the helper
`assemble_inference_messages` calls to recall, would have to pass `context.turn_id`, which it
already holds and already hands to the unavailable-memory warning beside the session.

What makes this smaller than it sounds is that the plumbing is two signatures and a call, and what
makes it larger is that the pairing target has no turn id of its own. `LoggingRecallSink` writes
`session_id` and never a turn, so a turn on the fallback would be unmatched by the very line it
exists to pair with until `RecallAudit` grows one too. That is a third signature and a value type,
and it is where the real decision is: whether a recall is a fact about a turn or a fact about a
session. Everything the trail carries today reads as the second.

## Trail

- 2026-08-20: Opened by the close of
  [R-316](316-a-rank-fallback-cannot-name-its-turn.md), which gave the port a session and found the
  turn its own title had asked for was a further two signatures away. Recorded in the ADR-0038
  named-recall addendum.
- 2026-09-13: Re-derived, and every signature this entry counts is still the shape it describes.
  `MemoryRecaller.recall(query, *, k, session_id)` takes no turn id, `RecallPolicy.select` carries
  `session_id` and nothing more, `RecallAudit` holds a `session_id` beside the query and the pool
  and no turn, and the judge's two warnings in `rerank_judge.py` write `session_id` into their
  `extra`. `assemble_inference_messages` still holds `context.turn_id` and still logs it beside the
  session on the unavailable-memory warning, so the value is where the entry says it is. One name
  corrected: the sink writes `session_id` rather than `session`, having been renamed to the
  vocabulary the seam and the stores share, which changes nothing about the pairing this asks for.
  The decision the entry names, whether a recall is a fact about a turn or about a session, is
  untaken, so it stays open rather than being plumbed on the way past.
- 2026-09-19: Re-derived; the change this entry waits for has not landed and none of its
  signatures moved. `MemoryRecaller.recall(query, *, k, session_id)` still takes no turn id,
  `RecallPolicy.select` still carries `session_id: str | None = None` and nothing more, and
  `RecallAudit` and `LoggingRecallSink` still hold and write `session_id` and no turn. The only
  commit to the recall code since 2026-09-13 moved per-policy tests into one shared check list.
  One path corrected above: the recall is made by `_recalled_context`, the helper
  `assemble_inference_messages` calls, not by that function itself; the helper holds the same
  `context` and predates this entry. One entry filed since bears on the cost:
  [R-683](683-the-recall-trail-has-no-store.md) would write the recall trail to a file while the
  judge's two fallback warnings stay on the log stream, which removes even the adjacency this
  entry says a busy brain already breaks. If it lands first, the turn id this entry adds has two
  trail adapters to reach rather than one.
