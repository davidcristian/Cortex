# A word for all after a named row and its value lists every row holding the value

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, `Forget the card 4242 everywhere.` and
`Forget my card 4242 everywhere.` with the call text `4242` delete all three, and with the call
text `phone` they delete the phone. `quantifies` (`forget_unnamed.py`) reads a word for all
within two words after a value as asking for every row, and reads a row word only between a
word for all and a value after it. `Forget the card 4242.` lists the card alone. This is the
unsafe direction: the card lists rows the message does not name.

## What to do

1. Write the near misses first: `Forget 4242 everywhere.` and `Forget the 4242 everywhere.` must
   list every row holding the value, as today.
2. In `quantifies`, do not count a value before the word for all when the word before that value
   names a matched row or is a kind word, as `_limited` reads the words after.
3. Replay the pools of [the readings](../../readings/forget-everything-unread-role.md), with
   messages added that hold each row word, the value and then each word for all.

## History

- 2026-11-15: filed from a probe beside the row word read between a word for all and the value.
