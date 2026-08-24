# Two spellings of one conversation across the brain's log fields

**Status:** landed 2026-08-24
**Area:** cross-cutting
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
- 2026-08-21: An eighth site landed under `session_id`, the tool audit line (ADR-0009 named-work
  addendum), chosen deliberately rather than by default: the trail's whole purpose is to be
  greppable beside the turn failure lines in `converse_stream`, which spell it that way. So the
  split is now six sites to two, and the argument for moving the trail and the judge to `session_id`
  is one site stronger, while the cost named above (a field a runbook tells an operator to grep) is
  unchanged.
- 2026-08-24: landed as the rename to `session_id`, decided together with
  [R-394](394-the-fired-item-has-two-spellings-in-the-logs.md) under one rule: a line names a work
  identity with the dispatch stamp's own name for it, and that vocabulary is the five `_id` names
  the stamp and the audit trail already carry. **The count above was short by one again.**
  Re-derived on the tree it is seven sites to two, not six: `engine.py`'s unreadable-tool-call
  warning attaches `session_id`, and it landed fifteen minutes after this entry was written and was
  missed when the trail was updated the next day. Counting lines rather than sites it is ten to
  three. **The last paragraph was wrong on both of its premises.** A log field's name is spent, as
  the string key opening an `extra=` dict, which is the bare-literal case the registry vocabulary
  already covers; and `crosscheck.py` is not cross-language only, two existing parts already tying
  Python to Python. What was missing was a declaring site, so `cortex_core.log_fields` now declares
  all five names, `LoggingAuditSink` spends them as the one sink that writes the vocabulary as a
  list, and `scripts/logcouplings.py` is a tenth registry part tying every literal and every
  runbook grep back to those declarations, proved able to fail twelve ways. The runbook cost was
  paid in the same change, both of its sentences updated. Tabled in the ADR-0009 one-vocabulary
  addendum, with what it cost this ADR's own two surfaces in the ADR-0038 one-name addendum and the
  new registry part in the ADR-0029 addendum beside them. Two narrower entries open in its place:
  the swap path's bare nouns, which is the third surface this shape was waiting for and was already
  in the tree ([R-415](415-the-swap-path-names-its-work-with-bare-nouns.md)), and the registry's
  blindness to a module nobody has listed yet
  ([R-416](416-a-new-log-line-can-name-its-work-anything.md)).
