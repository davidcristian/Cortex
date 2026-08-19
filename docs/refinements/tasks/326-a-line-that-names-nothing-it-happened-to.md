# A line that names nothing it happened to

**Status:** open, actionable
**Area:** cross-cutting
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Now that a record's fields reach the line, the sites that attach none of their own are the ones
worth reading again. Seventeen log calls in the brain attach no `extra` at all. Most are honest:
`_logger.exception("the handoff store failed before anything was evicted")` has a traceback and no
id worth naming beside it. Two kinds are not.

`cortex_session/schedule_claims.py` quarantines a record it could not decode with
`logger.error("quarantining corrupt schedule record %r to %r", item_id, DEAD_KEY)`, which spells
both values into the message and attaches neither. So the one line that says a schedule item was
moved out of the working set names the item in prose only: `grep` finds the sentence, nothing can
select on the id, and under `CORTEX_LOG_FORMAT=packed` the id sits inside the `message` string
rather than in `fields`. It is the mirror image of the family the twice-printed-field sweep closed,
and the fix is the same shape pointing the other way: the message keeps its words, the id and the
destination key become fields.

The second kind is a line that identifies nothing at all. `converse_stream` reports a session store
that failed mid-turn, an inference that failed mid-turn and an unexpected failure handling a turn,
none of them carrying the `turn_id` or `session_id` the turn is holding right there; `ticker`
reports a schedule fire that failed without the `reminder_id` it failed on, though the line beside
it that reports a failed push does carry one. On a machine serving one user these are readable from
what surrounds them. On a busy log they are the lines an operator finds and then cannot follow,
which is the whole reason the fields are printed now.

## Trail

- 2026-08-19: Opened by the close of
  [R-323](323-a-field-spelled-into-its-own-message.md), whose sweep of every message that spelled a
  field it carried had to read every log site in the brain, and found these at the other end of the
  same question.
