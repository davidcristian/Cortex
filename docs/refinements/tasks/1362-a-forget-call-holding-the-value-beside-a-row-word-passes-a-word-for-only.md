# A forget call holding the value beside a row word passes a word for only

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-26

`alone` (`forget_only.py`) reads the runs of the message after the call text, so on `Forget 4242,
the card too, only the phone.` the call text `4242` keeps the card and the locker, which the
reading "only the phone" keeps. A call text holding the value beside a word of the row, as `locker
4242`, `code is 4242` or the row's whole request `Remember that my locker code is 4242.`, is not
in the message, so `alone` finds no run and the card lists the locker. With the three rows seeded,
that call deleted the locker in 2 of 8 draws, and the same call texts list the locker on `Forget
all 4242, only the card.` at the run's start tree too
([readings](../../readings/forget-readers-live-draw.md#one-form-per-change)).

## What to do

1. Add these call texts to the generator for every form holding a word for only, in five
   languages, and count the rows asked to keep that the card lists.
2. Read the runs after the message's value that the call text holds, not after the call text, and
   replay over every set: no row newly listed, and the rows asked to delete newly kept as its cost.
   Then draw it with the rows seeded.

## History

- 2026-11-26: filed from the seeded draw of the word for only, the one form of eight that failed.
