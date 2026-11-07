# The numbers left note repeats a reply that names the row left in other words

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

`names_still_held` in `numbers_left_claim.py` reads only English `still` followed by a verb such as
`holds`, `stored`, `mentions` or `appears in`. A reply that says the number is still held in other words, or in one of the
four other languages the forgotten reader reads, still gets `NUMBERS_LEFT_NOTE`, which repeats what
the reply said. A needless note is the safe direction.

Reproduction, unit level (`SCRATCH/slot20/probe2.py`), `numbers_left_claim(reply, left=True)` is
`True` for each:

- "I've forgotten your door code. The number 1987 also appears in another memory."
- "J'ai oublié votre code, mais un autre souvenir contient encore 1987."
- "Ich habe den Türcode vergessen, aber 4512 steht noch in einer anderen Erinnerung."
- "I've forgotten it. One other memory holds 1987 too, so ask me to forget 1987 as well."

## What to do

1. Write near misses first ("it also appears that nothing was stored"), since a reader that
   reads one withholds a note the reply needs.
2. Read `also`, `too` and `encore`, `noch`, `todavía`, `încă` beside a verb of holding, with the
   negation of each language. The form is rare (0 of 121 recorded forget
   replies), so the pass rule is about what the reader does when the form occurs.

## History

- 2026-11-07: filed by the third audit of the night's changes.
- 2026-11-07: 0 of the 121 distinct replies recorded tonight for a turn that ran
  `forget_memories` name a row left in any words; left open for the reader change.
- 2026-11-07: the reader now also reads `still mentions` and `still appears in`; the other forms
  above stay open.
