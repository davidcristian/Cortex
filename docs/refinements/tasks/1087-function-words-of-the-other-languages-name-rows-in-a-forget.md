# Function words of the other languages name rows in a forget

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`_COMMON` in `forget_unnamed.py` lists English function words only, so a French, German, Spanish
or Romanian article or preposition of three or more letters counts as a word naming a fact. Unit
probes on 2026-11-09 over two German rows sharing 7319: `Vergiss 7319, behalte den vom Schuppen.`
keeps both rows, since `den` is in the bike row too, and nothing is deleted;
`Vergiss den Code von meinem Fahrradschloss, 7319.` names the shed row through `den` and lists it
for deletion. Spanish `del` and French `celui` or `les` do the same ([readings](../../readings/forget-keep-clause.md#second-audit-probes-2026-11-09)).

## What to do

1. Write the two German messages and Spanish and French forms over rows in their own language as
   tests first, with a near miss whose function word is the only word naming the row.
2. Add each language's articles, prepositions and pronouns of three or more letters to the common
   words, then replay every recorded forget string through the old and new reader.

## History

- 2026-11-09: filed by the second audit of the night's forget and schedule fixes, from unit probes.
