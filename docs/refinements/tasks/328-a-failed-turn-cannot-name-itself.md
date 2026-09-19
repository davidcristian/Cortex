# A failed turn can name its session but never itself

**Status:** done 2026-08-20
**Area:** session-read-rpc
**Origin:** [ADR-0046](../../adr/ADR-0046-work-identities-on-log-lines.md)

The three mid-turn failures in `converse_stream` attach `session_id`, which is all the stream holds
when a turn dies. The `turn_id` that would be more useful is created inside `TurnEngine`
(`turn_id_factory`) and leaves the engine only on the `TurnComplete` event a failed turn never
emits, so the handler that reports the failure has no id for the turn it was serving.

The cost is one join an operator cannot make. A session that failed three turns in a row prints
three lines under one `session_id`, and nothing says whether that is one repeating fault or three
unrelated ones; the audit lines and the tool-invocation lines the same turn wrote have no turn id
either.

Two designs would close it, differing in where the id is created. The stream could create the turn
id and hand it to `handle_turn`, which is a signature change to the `TurnRunner` port that every
implementation and its fakes follow. Or the engine could expose it earlier, as a first event or on
a small started-turn record in the session store, which keeps the port's shape but adds an event
whose only consumer is a log line. Neither should be picked without also asking whether the turn id
belongs on the tool-audit lines, since half the value is joining them.

## History

- 2026-08-19: Opened by the close of [326](326-a-line-that-names-nothing-it-happened-to.md), which
  gave those three lines the one identifier the handler has and recorded the one it does not.
- 2026-08-20: Fixed as the first design, the stream creating the turn id and handing it to
  `handle_turn`. Identity belongs to whoever can observe the whole of a turn, and the stream is the
  only side that sees a turn fail; the engine's own id was unreachable exactly where it was needed.
  `TurnEngine` lost its `turn_id_factory`, and the escalating wrapper, which had the same defect
  one level in, no longer reads its turn's identity off the inner completion. The paired question
  was answered yes and moved to [342](342-the-audit-trail-cannot-name-the-turn.md), the naming
  decision it forces being the audit trail's rather than this line's. Recorded in ADR-0046
  decision 9.
