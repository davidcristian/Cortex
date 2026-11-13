# A German request to remember calls the forget tool unasked

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

`forget_unrequested("Merke dir, meine Telefonnummer ist 0721 555 019.")` returns no tool, so the
forget tool stays on that turn, while `Remember that my gym code is 4242.` refuses it. On
`cortexn21-brain-s7kind` all 4 store turns of that message called `forget_memories`, which matched
nothing, and the reply closed with the German note for a forget that found nothing; the row was
stored each time ([readings](../../readings/forget-kind-and-value-names.md#a-negation-read-per-clause)).

## What to do

1. Find which reader of `memory_request.py` misses `Merke dir,` followed by a statement, and
   write it and its near misses (`Merke dir das nicht, vergiss meine Nummer.`, which asks to
   forget) as tests.
2. Refuse the tool only on the positively named form, then replay the recorded forget strings and
   draw the store turn and the neighbouring forgets.

## History

- 2026-11-13: filed from the draws of the kind word read per clause.
