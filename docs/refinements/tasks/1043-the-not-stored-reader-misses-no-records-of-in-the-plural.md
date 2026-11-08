# The not stored reader misses no records of in the plural

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-08

`says_not_stored` in `forget_unfound_claim.py` reads `no record of`, `no memory of`, `no entry of`
and `no entries of`, but not `no records of` or `no other records of`. A reply after a delete and a
call that matched nothing that says "there were no records of the locker combination" says the
deleted fact was never stored and gets no `DELETED_UNFOUND_NOTE`. Unit level, `says_not_stored` is
`False` for both:

- "there were no records of the locker combination."
- "there were no other records of that found to remove."

The second is lk7 of the live draws
([readings](../../readings/forget-later-call-other-words.md#live-draws-on-the-build-2026-11-08)),
which says no other record was found; that is true, so it needed no note, but the first form is
the false claim.

## What to do

1. Write near misses first: "no other records of it remain" and "no records of it are kept now"
   say the delete held and must not be read.
2. Read `records` beside `no` and `of`, and `other` between them, only with a verb of finding or
   storing (`found`, `stored`, `saved`, `had`) or none. A reply note shows when unsure.

## History

- 2026-11-08: filed by the slot that built `DELETED_UNFOUND_NOTE`, from lk7 of its live draws.
