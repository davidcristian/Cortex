# Two names for one conversation across the brain's log fields

**Status:** done 2026-08-24
**Area:** cross-cutting
**Origin:** [ADR-0046](../../adr/ADR-0046-work-identities-on-log-lines.md)

Seven log sites in the brain attach the conversation a line is about, under two different names.
`session` is the recall trail (`LoggingRecallSink`) and, since the rank's fallbacks were named
(ADR-0038 decision 15), the judge's two fallback warnings. `session_id` is everything else: the
dropped-recall warning in `turn_context.py`, the unrecorded-memory error in `turn_output.py`, the
lost-recap warning in `summarizing.py`, and the three failure lines plus the stream line in
`converse_stream.py`.

The judge's name was chosen rather than defaulted: a fallback is read beside the trail line for the
same recall, so the two have to be findable with one grep, and the trail is the older of the pair.
That does not settle the other five.

The fix is a rename in one direction or the other. Moving the trail and the judge to `session_id`
touches a field [docs/runbooks/memory-pgvector.md](../../runbooks/memory-pgvector.md) tells an
operator to grep. Moving the other five to `session` is a wider edit that nothing outside the tree
reads, and it leaves `turn_id` beside it looking odd, since `turn` would then be the matching name
and nothing uses it.

## History

- 2026-08-20: Opened by the close of [R-316](316-a-rank-fallback-cannot-name-its-turn.md), which
  added the seventh site and the second under the trail's name. Recorded in ADR-0038 decision 15.
- 2026-08-21: An eighth site arrived under `session_id`, the tool audit line (ADR-0009 decision
  16), chosen deliberately: the trail exists to be read beside the turn failure lines in
  `converse_stream`, which use that name. The split is now six sites to two.
- 2026-08-24: Fixed as the rename to `session_id`, decided together with
  [R-394](394-the-fired-schedule-item-has-two-field-names-across-the-brains.md) under one rule: a line names a work
  identity with the dispatch stamp's own name for it, and that vocabulary is the five `_id` names
  the stamp and the audit trail already use. The count above was short by one again: counted from
  the tree it is seven sites to two, not six, since `engine.py`'s unreadable-tool-call warning
  attaches `session_id` and was added fifteen minutes after this entry was written. Counting lines
  rather than sites it is ten to three. The last paragraph of the original entry was wrong on both
  of its premises: a log field's name is used as the string key opening an `extra=` dict, which is
  the bare-literal case the registry vocabulary already covers, and `crosscheck.py` is not
  cross-language only, two existing parts already comparing Python to Python. What was missing was
  a declaring site, so `cortex_core.log_fields` now declares all five names, `LoggingAuditSink`
  uses them as the one sink that writes the vocabulary as a list, and `scripts/logcouplings.py` is
  a tenth registry part comparing every literal and every runbook grep back to those declarations,
  proved able to fail twelve ways. The runbook was updated in the same change. Decided in ADR-0046
  decision 1, with the new registry part in ADR-0042. Two narrower entries open in its place: the
  swap path's bare nouns ([R-415](415-the-swap-path-names-its-work-with-bare-nouns.md)) and the
  registry's blindness to a module nobody has listed yet
  ([R-416](416-a-new-log-line-can-name-its-work-anything.md)).
