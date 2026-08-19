# A failed turn can name its session but never itself

**Status:** open, actionable
**Area:** session-read-seam
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The three mid-turn failures in `converse_stream` now carry `session_id`, which is the whole of what
the stream honestly holds when a turn dies. The `turn_id` it would rather carry is minted inside
`TurnEngine` (`turn_id_factory`) and leaves the engine only on the `TurnComplete` event a failed
turn never emits, so the handler that reports the failure has no id for the turn it was serving.

The cost is one join an operator cannot make. A session that failed three turns in a row prints
three lines under one `session_id`, and nothing on them says whether that is one repeating fault or
three unrelated ones; the audit lines and the tool-invocation lines the same turn wrote carry no
turn id either, so a failure cannot be tied to the work that preceded it. On a machine serving one
user this is read from the surrounding lines. It is exactly the reading the fields were printed to
end.

Two shapes would close it and they differ in where the id is born. The stream could mint the turn
id and hand it to `handle_turn`, which makes the id part of the seam's own vocabulary and is a
signature change to the `TurnRunner` port that every implementation and its fakes follow. Or the
engine could surface it earlier, as a first event or on a small started-turn record in the session
store, which keeps the port's shape but adds an event whose only consumer is a log line. The first
is cleaner and larger; the second is cheaper and leaves the id optional, which is how a field ends
up missing exactly when it matters. Neither should be picked without also asking whether the turn
id belongs on the tool-audit lines, since half the value here is joining them.

## Trail

- 2026-08-19: Opened by the close of
  [326](326-a-line-that-names-nothing-it-happened-to.md), which gave those three lines the one
  identifier the handler holds and recorded the one it does not.
