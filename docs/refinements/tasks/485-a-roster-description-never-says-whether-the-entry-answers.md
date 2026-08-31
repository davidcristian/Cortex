# A roster entry's description tells the cortex how fast it is and never whether it answers

**Status:** declined 2026-08-30
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)

Opened 2026-08-28 by the close of
[R-483](483-the-rest-of-the-subagent-tier-is-unasked.md), which finished measuring the subagent row
and found its entries 28 points apart on the one property the cortex cannot see.

`SubagentProfile` carries a `description` that is advertised to the cortex verbatim, and it is the
whole of what the cortex picks an entry by. The one alternate a compose file ships describes itself
as "small and fast; weaker against prompt injection, so only offered for trusted text-only
subtasks", which names a speed and a hazard. Both are true. Neither is the property that decides
whether the delegated answer arrives.

All five entries of the subagent row have now been run through the shipped constrained reply path at
288 runs each, and they deliver an answer on the same narrow work between **66 and 94 of 96**
([ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)'s row addendum). The spread is not
where a reader would guess: it is not monotone in size across families, the shipped default sits in
the middle of it, and the entry that describes itself as small and fast is a full shape worse than
another entry nobody mentions. A cortex choosing on the advertised text is choosing on speed and
robustness while the thing it actually needs, an answer rather than a plan, varies more between
entries than either.

**What is wrong with the present shape.** Nothing in the wiring is wrong; the description is doing
what ADR-0018 says it does. What is missing is that a measured, per-entry, decision-relevant number
exists in this repo and reaches no chooser. It sits in an ADR table. A deployment that adds a roster
entry writes a description by hand, from taste, with no place to put a rate even if it had one.

**What would close it, and the three shapes it could take.** They are worth pricing against each
other before one is built.

1. **A sentence, per entry, in the description.** Free, immediate, and false the day the wording or
   the engine build changes, since nothing holds a hand-typed rate to a measurement.
2. **A field on `SubagentProfile`** carrying the measured delivered rate and what it was measured
   on, rendered into the advertised text by the spec builder rather than typed into it. A port
   change, and the same port change
   [R-482](482-the-sentence-is-one-wording-for-every-entry.md) needs for its per-entry wording, so
   the two should be designed together or one will be built twice.
3. **Nothing, deliberately**, on the argument that the cortex should not be choosing on a rate it
   cannot verify and that the right home for this is the operator's runbook, where it now is. This
   is a real option and it is the one to argue against explicitly rather than skip.

## Trail

- 2026-08-28: opened by the close of
  [R-483](483-the-rest-of-the-subagent-tier-is-unasked.md), which measured the last two entries of
  the row and put the spread in delivered answers at 66 to 94 of 96 across the five.
- 2026-08-30: declined by the ADR-0018 addendum on the description staying trade-off text. The
  premise held: `description` is advertised verbatim by `_model_property` and is the whole of what
  distinguishes one entry from another to a chooser. Shape 3 is chosen, and the three reasons the
  2026-07-16 addendum could not have given are that a rate names a roster entry while an entry does
  not fix a model (the same finding that declined
  [R-482](482-the-sentence-is-one-wording-for-every-entry.md)), that a rate is a reading under four
  conditions no profile can see and a fifth that is hand judged, and that the chooser was measured
  reaching for the knob on one of fifteen recorded batches in the one wiring where it is advertised
  at all. The rates stay in the operator's runbook, where the reader can also see the conditions and
  change the pick, and that table now carries them. Opens
  [R-508](508-a-roster-entry-names-an-endpoint-and-not-a-model.md).
