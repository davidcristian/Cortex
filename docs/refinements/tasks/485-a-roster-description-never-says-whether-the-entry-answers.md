# A roster entry's description tells the cortex how fast it is and never whether it answers

**Status:** declined 2026-08-30
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)

`SubagentProfile` has a `description` that is advertised to the cortex word for word, and it is the
whole of what the cortex picks an entry by. The one alternate a compose file ships describes itself
as "small and fast; weaker against prompt injection, so only offered for trusted text-only
subtasks", which names a speed and a hazard. Both are true. Neither is the property that decides
whether the delegated answer arrives.

All five entries of the subagent row have been run through the shipped constrained reply path at
288 runs each, and they deliver an answer on the same narrow work between 66 and 94 of 96 (the
five-pick envelope review of 2026-08-28, [reply envelope](../../readings/reply-envelope.md)). The
spread is not where a reader would guess: it is not monotone in size across families, the shipped
default sits in the middle, and the entry that describes itself as small and fast is a full shape
worse than another entry nobody mentions. The measured number exists in this repo and reaches no
chooser; it sits in an ADR table.

## History

- 2026-08-28: opened by the close of
  [R-483](483-the-rest-of-the-subagent-tier-is-unasked.md), which measured the last two entries of
  the row and put the spread in delivered answers at 66 to 94 of 96 across the five.
- 2026-08-30: declined by ADR-0018 decision 10, the description staying trade-off text. The premise
  held: `description` is advertised word for word by `_model_property` and is the whole of what
  distinguishes one entry from another to a chooser. Of the three options, a hand-typed rate in the
  description and a measured rate on `SubagentProfile` were both rejected and doing nothing was
  chosen, for three reasons the 2026-07-16 decline could not have given: a rate names a roster entry
  while an entry does not fix a model (the same finding that declined
  [R-482](482-the-sentence-is-one-wording-for-every-entry.md)), a rate is a reading under four
  conditions no profile can see and a fifth that is judged by hand, and the chooser was measured
  reaching for the setting on one of fifteen recorded batches in the one wiring where it is
  advertised at all. The rates stay in the operator's runbook, where the reader can also see the
  conditions and change the pick, and that table now has them. Opens
  [R-508](508-a-roster-entry-names-an-endpoint-and-not-a-model.md).
