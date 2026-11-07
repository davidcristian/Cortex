# The numbers left note repeats a reply that names the row left in other words

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

`names_still_held` in `numbers_left_claim.py` reads only English `still` followed by a verb such as
`holds` or `stored`. A reply that says the number is still held in other words, or in one of the
four other languages the forgotten reader reads, still gets `NUMBERS_LEFT_NOTE`, which repeats what
the reply said. A needless note is the safe direction.

Reproduction, unit level (`SCRATCH/slot20/probe2.py`), `numbers_left_claim(reply, left=True)` is
`True` for each:

- "I've forgotten your door code. The number 1987 also appears in another memory."
- "I've forgotten your door code, though another exchange still mentions 1987."
- "J'ai oublié votre code, mais un autre souvenir contient encore 1987."
- "Ich habe den Türcode vergessen, aber 4512 steht noch in einer anderen Erinnerung."
- "I've forgotten it. One other memory holds 1987 too, so ask me to forget 1987 as well."

## What to do

1. Count how many recorded turn d replies in `docs/readings/forget-value-repeats.md` name the row
   left at all; if none do, record that and leave the reader as it is.
2. Otherwise read `also`, `too`, `mentions`, `appears` and `encore`, `noch`, `todavía`, `încă`
   beside a verb of holding, with near misses first ("nothing still mentions it").

## History

- 2026-11-07: filed by the third audit of the night's changes.
