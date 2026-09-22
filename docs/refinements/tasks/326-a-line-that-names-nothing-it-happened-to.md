# A line that names nothing it happened to

**Status:** done 2026-08-19
**Area:** cross-cutting
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

Now that a record's fields reach the line, the sites that attach none of their own are worth
reading again. Seventeen log calls in the brain attach no `extra` at all. Most are justified:
`_logger.exception("the handoff store failed before anything was evicted")` has a traceback and no
id worth naming beside it. Two kinds are not.

`cortex_session/schedule_claims.py` quarantines a record it could not decode with
`logger.error("quarantining corrupt schedule record %r to %r", item_id, DEAD_KEY)`, which writes
both values into the message and attaches neither. So the one line that says a schedule item was
moved out of the working set names the item in prose only: `grep` finds the sentence, nothing can
select on the id, and under `CORTEX_LOG_FORMAT=packed` the id sits inside the `message` string
rather than in `fields`. The fix is the message keeping its words while the id and the destination
key become fields.

The second kind identifies nothing at all. `converse_stream` reports a session store that failed
mid-turn, an inference that failed mid-turn and an unexpected failure handling a turn, none of them
with the `turn_id` or `session_id` the turn is holding right there; `ticker` reports a schedule
that failed to run without the `reminder_id` it failed on, though the line beside it that reports a
failed push has one. On a machine serving one user these are readable from what surrounds them. On
a busy log they are the lines an operator finds and then cannot follow.

## History

- 2026-08-19: Opened by the close of [R-323](323-a-field-written-into-its-own-message-now-prints-twice.md), whose
  pass over every message that wrote a field it already attached had to read every log site in the
  brain, and found these at the other end of the same question.
- 2026-08-19: Fixed as ADR-0051 decision 7. Counted from the tree first with an AST pass over all
  91 `logger.*` calls in the brain, which confirmed the 17: nine were judged justified and left
  exactly as they are (three conditions with no subject, two failures covering two candidate
  models, three store reads that fail before an id exists, and the pump's own failure, which is not
  about a turn), and eight were converted. The quarantine line keeps its words and attaches
  `item_id` and `dead_key`, with the traceback one frame up attaching `item_id` too so one id finds
  both; `converse_stream`'s three turn failures and its ignored-event line attach `session_id`, and
  the ignored event also attaches the payload `kind` that would name an unhandled new member of the
  oneof; the ticker's failure now reads its id off the claim `gather` answered for (the results are
  zipped with the claims rather than filtered out of them) and its release failure off the claim it
  was releasing, both as `reminder_id`, the name the push line beside them already uses. No user
  content was attached anywhere: a turn holds the user's own text and the formatter's list of
  withheld names cannot see content, so the test asserts the absence as well as the presence.
  Verified live twice on a running stack, a planted corrupt record quarantined by the ticker's own
  pass, once in `plain` (the id printed once per line) and once under `CORTEX_LOG_FORMAT=packed`
  (the id under `fields`, the message constant). `docs/runbooks/scheduling.md` gained the grep it
  could not offer while the id was prose. It opened
  [328](328-a-failed-turn-cannot-name-itself.md), the turn id no failed turn can name, and
  [329](329-a-failure-with-two-candidate-subjects.md), the two lines whose failure has two
  candidate models.
