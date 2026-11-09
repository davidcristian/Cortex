# A compound code word names no fact in a forget

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`code_word` in `memory_values.py` matches a whole word ending in a code word, so `doorcode`,
`Fahrradcode` or `Türnummer` counts as a code word and names no fact in `unnamed`
(`forget_unnamed.py`). A message naming its fact only by such a compound then reads as naming the
value alone, and every row holding the value is listed for deletion. Unit calls on 2026-11-09 over
a door row, a shed row and a German bike row sharing 7319: `Forget the doorcode 7319, keep
everything else.` and `Vergiss den Fahrradcode 7319, alles andere bleibt.` keep no row, while
`Forget my door code 7319, keep everything else.` keeps the shed and bike rows
([readings](../../readings/forget-keep-clause.md#function-words-of-the-other-languages-2026-11-09)).
German writes most such names as one compound. This is the destructive card's unsafe direction,
although the card lists every row before anything is deleted.

## What to do

1. Write near misses as tests first: `Forget 7319.` and `Forget the code 7319.` still ask for every
   row, and `Forget my passcode 7319.`, where the part before the code word names no fact.
2. Read the part of a compound before its code word as a word naming a fact, matched against a
   row word it starts (`fahrrad` in `fahrradschloss`), then replay every recorded forget string
   through the old and new reader.

## History

- 2026-11-09: filed from the replay of the function word change to the forget reader, from unit
  probes (`probe1.py` in the night's scratchpad `slot14/`).
