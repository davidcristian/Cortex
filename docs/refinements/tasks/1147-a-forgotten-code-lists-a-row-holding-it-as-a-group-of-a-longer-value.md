# A forgotten code lists a row holding it as a group of a longer value

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-11

A forget whose text is a short code that the person's message also names lists, on the
destructive card, a row that holds the code only as one space-separated group of a longer value.
A unit call on 2026-11-11 with one row,
`User: My IBAN is RO49 AAAA 1B31 0075 9384 0000.`, and a call of `0075` for
`Forget the code 0075.` showed a card listing the IBAN row with no keep line, and the invoke
deleted it. A call of `1111 4242` for a row holding the card `4111 1111 1111 4242` did the same.
`inside` (`forget_inside.py`) keeps a match only where a letter or digit touches the text, so
spaces on both sides read as a whole token, and `longer` (`forget_longer.py`) keeps a row only
when the message lacks the call's value. The safe direction of the card keeps rows.

## What to do

1. Write near misses as tests first: `4242` for `Forget the card ending in 4242.` still deletes
   the card row, and a row holding the code alone (`door code 0075`) is still listed.
2. Keep a literal match whose text is one group of a longer whole value (`whole_values` in
   `memory_values.py`) and show it under `INSIDE_LINE`, unless the message names the longer
   value's kind (`card`, `account`) or the text is its last group.

## History

- 2026-11-11: filed from the third audit of the night's forget changes, with the unit call above.
