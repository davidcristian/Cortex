# A named recall is not a named turn

**Status:** open, a seam or port change comes first
**Area:** memory
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

`RecallPolicy.select` now carries a `session_id`, so the judge's two fallback warnings name the
conversation they happened in. They still cannot name the recall. A session with twenty turns
produces twenty recalls, every one of them logging the same `session`, so a fallback and the trail
line for the recall it belongs to are joined only by adjacency in the stream, which is exactly what
stops holding on a busy brain and on any collector that reorders.

The gap is one level further back than the one just closed. `MemoryRecaller.recall(query, *, k,
session_id)` takes no turn id either, so widening the policy port alone reaches nothing: the method
would have to grow one, and `assemble_inference_messages` would have to pass `context.turn_id`,
which it already holds and already logs beside the session when memory is unavailable.

What makes this smaller than it sounds is that the plumbing is two signatures and a call, and what
makes it larger is that the pairing target has no turn id of its own. `LoggingRecallSink` writes
`session` and never a turn, so a turn on the fallback would be unmatched by the very line it exists
to pair with until `RecallAudit` grows one too. That is a third signature and a value type, and it
is where the real decision is: whether a recall is a fact about a turn or a fact about a session.
Everything the trail carries today reads as the second.

## Trail

- 2026-08-20: Opened by the close of
  [R-316](316-a-rank-fallback-cannot-name-its-turn.md), which gave the port a session and found the
  turn its own title had asked for was a further two signatures away. Recorded in the ADR-0038
  named-recall addendum.
