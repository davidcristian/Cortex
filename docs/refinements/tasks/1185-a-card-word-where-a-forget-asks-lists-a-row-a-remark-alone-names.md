# A card word where a forget asks lists a row a remark alone names

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-13

`inside` (`forget_inside.py`) keeps a row that holds the call's text only as a group of a longer
value and that only a remark of the message names
([the remark reader](../../readings/forget-remark-about-the-value.md)). `_grouped` keeps no such
row once the part of the message that asks names `card`, `account` or `IBAN` (`_KIND`), whichever
row the kind word names. With the rows `Remember that my locker code is 4242.`, `Remember that my
card is 4111 1111 1111 4242.` and `Remember that my phone is 0721 555 4242.`, the call text `4242`
and the message `Forget the locker code 4242 and the card, I texted both from my phone.`, the card
lists and deletes the phone row too, which only the remark `I texted both from my phone` names.
HEAD `22655613b` does the same. The person still sees the card before the delete.

## What to do

1. Write tests first: the message above lists the locker and card rows and keeps the phone row;
   `Forget my card 4111.` beside the card still lists the card.
2. Apply `_KIND` only to a row the asking part names, and keep every other row's group check.
3. Replay every recorded message and test string through the card.

## History

- 2026-11-13: filed while building the remark reader, which left this form unchanged.
