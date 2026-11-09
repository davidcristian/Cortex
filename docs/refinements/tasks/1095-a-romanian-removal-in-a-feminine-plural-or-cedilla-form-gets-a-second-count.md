# A Romanian removal in a feminine, plural or cedilla form gets a second count

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-09

`_REMOVED` in `numbers_left_claim.py` reads `șters`, `uitat` and `eliminat` but not `ștearsă`,
`șterse`, `uitată`, `uitate`, `eliminată` or the cedilla `şters`. `Amintirea a fost ștearsă.` names
the removal, and the count note follows it in Romanian. The note is true, so the cost is a repeat
([readings](../../readings/forget-count-note.md#second-audit-probes-2026-11-09)).

## What to do

Write the forms above and a negated one (`nu a fost ștearsă`) as tests first, then widen the
pattern and replay the recorded reply strings through `says_forgotten`.

## History

- 2026-11-09: filed by the second audit of the night's forget and schedule fixes, from unit probes.
