# A line that names nothing it happened to

**Status:** landed 2026-08-19
**Area:** cross-cutting
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Now that a record's fields reach the line, the sites that attach none of their own are the ones
worth reading again. Seventeen log calls in the brain attach no `extra` at all. Most are justified:
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
- 2026-08-19: Landed as the ADR-0038 named-subject addendum. Re-derived from the tree first with
  an AST pass over all 91 `logger.*` calls in the brain, which confirmed the **17**: nine were
  judged honest and left exactly as they are (three pass guards with no subject, two failures
  wrapping two candidate models, three store reads that fail before an id exists, and the pump's
  own failure, which is not about a turn), and eight were converted. The quarantine line keeps its
  words and carries `item_id` and `dead_key`, with the traceback one frame up carrying `item_id`
  too so one id finds both; `converse_stream`'s three turn failures and its ignored-event line
  carry `session_id`, and the ignored event also carries the payload `kind` that would name an
  unhandled new member of the oneof; the ticker's fire failure now reads its id off the claim
  `gather` answered for (the results are zipped with the claims rather than filtered out of them)
  and its release failure off the claim it was releasing, both as `reminder_id`, the name the push
  line beside them already uses. No user content was attached anywhere: a turn holds the user's own
  text and the formatter's denylist cannot see content, so the test asserts the absence as well as
  the presence. Verified live twice on a running stack, a planted corrupt record quarantined by the
  ticker's own pass, once in `plain` (the id printed once per line) and once under
  `CORTEX_LOG_FORMAT=packed` (the id under `fields`, the message constant), which is the claim this
  entry made. `docs/runbooks/scheduling.md` gained the grep it could not offer while the id was
  prose. What it opened is
  [328](328-a-failed-turn-cannot-name-itself.md), the turn id no failed turn can name, and
  [329](329-a-failure-with-two-candidate-subjects.md), the two lines whose failure has two
  candidate models.
