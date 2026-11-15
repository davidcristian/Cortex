# A word for all before a row word in a form no stored row holds lists every row

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, `Forget all lockers 4242.` with the call
text `4242` deletes all three, and with the call text `phone` it deletes the phone. `quantifies`
(`forget_unnamed.py`) stops a word for all at a word between it and the value only when that
word names a matched row or is a kind word, and `lockers` names no row, since the row holds
`locker`. `Forget all locker 4242.` lists the locker code alone, and `Forget the lockers 4242.`
keeps all three. The Romanian `dulapul` beside a row holding `dulap` reads the same way: 600
rows of the [replay](../../readings/forget-everything-unread-role.md#a-row-named-between-a-word-for-all-and-the-value-2026-11-15).
This is the unsafe direction: the card lists rows the message does not name.

`Forget my bike lock code, it is 7319, and every other 7319 too.` asks for every row, and its
tests in `test_forget_unnamed.py` and `test_forget_unnamed_reader.py` hold that. So a word
between that names no row cannot keep every row without a reading that tells `other` from
`lockers`.

## What to do

1. Write the near misses first: `every other 4242`, `every single 4242` and `all these 4242`
   must list every row holding the value, as today.
2. Read a word between as naming a row when a row word starts it or it starts a row word, as
   `lockers` and `dulapul` do, or keep the rows whose fate differs when the word between is no
   function word and names no row.
3. Replay the pools of the readings and the generated messages of `kindgen.py`, with a plural
   of each row word added.

## History

- 2026-11-15: filed from the replay of the row word read between a word for all and the value,
  where the Romanian `dulapul` and the plural `lockers` still listed every row.
