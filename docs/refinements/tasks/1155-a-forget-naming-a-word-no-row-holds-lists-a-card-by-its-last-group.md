# A forget naming a word no row holds lists a card by its last group

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

With only `Remember that my card is 4111 1111 1111 4242.` stored, `Forget my gym code.` with the
call text `4242` lists and deletes the card row. `inside` (`forget_inside.py`) keeps a last group
alone only when another row holds the text whole, and `unnamed` (`forget_unnamed.py`) keeps a row
the message names no word of only when its request holds the value whole, which a card ending in
`4242` does not. The message names `gym`, a word of no row, and the destructive card's safe
direction keeps rows. `Forget the code 4242.` names no word and should still list the card
([readings](../../readings/forget-last-group-beside-whole.md)).

## What to do

1. Write the rows as unit tests first: the card row alone, the text `4242`, and the messages
   `Forget my gym code.` (keeps the card), `Forget the code 4242.`, `Forget 4242.` and
   `Forget the card ending in 4242.` (each lists it).
2. Keep a row that holds the text only as a last group when the message names a word that no
   match holds, then replay the recorded forget strings through the old and new code.

## History

- 2026-11-12: filed from the unit rows of the last group keep beside a row holding the code whole.
