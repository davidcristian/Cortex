# A forget naming a card in other words deletes the code beside it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-12

With `Remember that my card is 4111 1111 1111 4242.` and `Remember that my gym code is 4242.`
stored, `Forget my Visa ending 4242.` or `Forget the number ending 4242.` with the call text `4242`
keeps the card under `INSIDE_LINE` and lists the gym code row. `inside` (`forget_inside.py`) keeps
a last group beside a row holding the text whole when the message names no word only the last group
row has, and `visa` and `ending` are words of neither row, so an approved card deletes the row the
message did not ask for and keeps the one it did. Before that keep, both rows were listed
([readings](../../readings/forget-last-group-beside-whole.md)).

## What to do

1. Write the rows as unit tests first: the card and the gym code, the text `4242`, and `Forget my
   Visa ending 4242.` and `Forget the number ending 4242.` (each lists the card), `Forget the code
   4242.` and `Forget my gym code.` (each lists the gym row and keeps the card).
2. Decide the listing when the message names words neither row holds beside a value it holds, then
   replay the recorded forget strings through the old and new code.

## History

- 2026-11-12: filed from the near misses of the last group keep with no row holding the code whole.
