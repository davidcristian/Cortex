# Two spellings of one conversation across the brain's log fields

**Status:** open, fix when it bites
**Area:** cross-cutting
**Trigger:** an investigation that reads one spelling and misses lines carrying the other, or a
third spelling of the same fact arriving on a new sink
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Seven log sites in the brain attach the conversation a line is about, and they attach it under two
names. `session` is the recall trail (`LoggingRecallSink`) and, since the named-recall addendum,
the judge's two fallback warnings. `session_id` is everything else: the forgone-recall warning in
`turn_context.py`, the unrecorded-memory error in `turn_output.py`, the lost-recap warning in
`summarizing.py`, and the three failure lines plus the stream line in `converse_stream.py`.

The judge's spelling was chosen rather than defaulted, and the choice stands on its own: a
fallback is read beside the trail line for the same recall, so the two have to be greppable
together, and the trail is the older of the pair. What that argument does not do is settle the
other five, which now diverge from both.

Fixing it is a rename in one direction or the other, and the two directions have different costs.
Moving the trail and the judge to `session_id` touches a field
[docs/runbooks/memory-pgvector.md](../../runbooks/memory-pgvector.md) tells an operator to grep,
and a shipped trail's field names are the closest thing this repo's logs have to an interface.
Moving the other five to `session` is a wider edit that nothing outside the tree reads, and it
leaves `turn_id` beside it looking odd, since `turn` would then be the matching name and nothing
spells it that way. Neither is obviously right, which is why this is written down rather than
guessed at.

The general shape underneath is that a field name is a value spelled in several places with
nothing tying the spellings together, which is what `crosscheck.py` exists for; it ties values a
far side declares or spends, and a log field's name is neither, so registering this family would be
a new kind of entry rather than another row.

## Trail

- 2026-08-20: Opened by the close of
  [R-316](316-a-rank-fallback-cannot-name-its-turn.md), which added the seventh site and the second
  one under the trail's spelling. Recorded in the ADR-0038 named-recall addendum.
