# The keep claim reader misses "I'll make sure to remember"

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-10

In c3 draw 1 of [the readings](../../readings/correction-keeps-old-value.md), `My sister's name is Hannah, not Anna.` called `list_allowed_directories`, so
the turn stayed out of memory, and the reply `Got it. I'll make sure to remember that your sister's
name is Hannah, not Anna.` ended with no `UNKEPT_CLAIM_NOTE`. A new chat answered Anna.
`claims_kept` (`memory_claim.py`) returns false on that reply and true on `I'll remember that your
sister's name is Hannah.`

## What to do

1. Write near misses first: `Make sure to remember it yourself.`, a question (`Should I make sure to
   remember it?`), a negation and a condition, then replay every recorded reply in `docs/readings/`
   through the old and new reader with counts.
2. Read `make sure to remember` and `make sure I remember` as a keep claim. A reply note shows, so a
   miss on the showing side is the safe one.

## History

- 2026-11-10: filed from c3 draw 1 in [the readings](../../readings/correction-keeps-old-value.md).
