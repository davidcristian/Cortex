# A clause adding two rows to a forget is a remark

**Status:** done 2026-11-15
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`_adds` (`forget_clauses.py`) reads a clause as adding to a forget only when it holds one word for
the or my and then fact words, so `the phone and the locker too` is a remark. Beside a card and a
phone ending `4242` and a locker code `4242`, `Forget the card 4242, the phone and the locker
too.` and `Forget the card 4242, my phone and my locker too.` delete the card and the locker and
keep the phone, which the message asks to delete. The start build of 2026-11-14 deleted all three:
it read the whole message, since no row holding the value whole was named by the asking part. A
misread here keeps the row, and the card shows it as kept, so the person can ask again.

## What to do

1. Write tests first: the two messages above delete all three rows, and `Forget the card 4242,
   keep the locker, my phone too.` still keeps the phone.
2. Read a list joined by a word for and inside an adding clause in `_adds`, each item a word for the
   or my and fact words.
3. Replay the forget card over every string literal of the brain's forget tests and the probes
   of [forget-remark-about-the-value.md](../../readings/forget-remark-about-the-value.md), before
   and after, and count rows newly deleted: each must be one the message asks to delete.

## History

- 2026-11-14: filed by the audit of the night's forget clause changes.
- 2026-11-15: done. `_adds` reads a list of items joined by `and`, `et` or `und`, each a word for
  the or my and then fact words, so both messages delete all three rows, and `Forget the card
  4242, keep the locker, my phone too.` still keeps the phone. A word for or joins no list. The
  replay changed 17 of 3,252 cases, 101 rows newly deleted and none newly kept, each one a list
  item names ([readings](../../readings/forget-added-list.md)). A first item before a comma stays
  a remark: [task 1205](1205-a-first-item-before-a-comma-in-a-list-adding-rows-is-a-remark.md).
