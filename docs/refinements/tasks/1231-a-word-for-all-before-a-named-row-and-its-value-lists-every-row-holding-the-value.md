# A word for all before a named row and its value lists every row holding the value

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.`, `Remember that my phone is 0721 555 4242.` and `Remember that my gym code is 7391.`,
`Forget every card 4242.` with the call text `4242` deletes the locker code and the phone with
the card, and with the call text `phone` it deletes the phone. `quantifies` (`forget_unnamed.py`)
reads a word for all within two words of a value as asking for every row holding the value, and
here `card` is between them. `Forget every 4242 card.` and `Forget every card ending 4242.` list
the card alone. This is the unsafe direction: the card lists rows the message does not name.

The table of forms (`forget_forms.py`) reads `jede`, `jeden`, `jedes` and `toute` as words for
all, so `Vergiss jede card 4242.`, `Vergiss jeden card 4242.` and `Oublie toute card 4242.` now
list all three rows, where each listed the card alone while those words were unread. The replay
that filled the four cells held no message with a row named between the word and the value.

## What to do

1. Write the near misses first: `Forget every 4242.`, `Forget all the 4242.`, `Forget all my
   4242.` and `Forget all of 4242.` must list every row holding the value, as today.
2. In `quantifies`, do not count a value as beside the word for all when a word between them is a
   kind word (`kinds` in `forget_kinds.py`), or let its caller pass the words that name a stored
   row, so the named rows alone are listed, as for `Forget every card ending 4242.`.
3. Replay the pools of [the readings](../../readings/forget-everything-unread-role.md), counting
   each row newly kept by what the message asks, with messages added that hold each word for all
   before a named row and the value.

## History

- 2026-11-15: filed from the audit replay of the table of forms, where `Vergeet jede card 4242.`
  with the call text `4242` newly listed the locker code and the phone.
