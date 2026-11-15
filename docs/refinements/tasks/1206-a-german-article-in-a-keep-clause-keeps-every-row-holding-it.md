# A German article in a keep clause keeps every row holding it

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Merke dir, der Code vom Spind ist 4242.`, `Merke dir, meine Karte ist 4111 1111 1111
4242.` and `Merke dir, mein Handy ist 0721 555 4242.`, with the call text `4242`, the message
`Vergiss alle 4242 außer der Karte.` keeps all three rows, while `Vergiss alle 4242, behalte die
Karte.` deletes the locker row. `_split` (`forget_unnamed.py`) reads the words of a keep clause
without the function words of the reading language, so `der` is a keep word, and `names` finds it
in the locker row's text. This keeps a row, the safe direction, and the kept note shows it.

## What to do

1. Write tests first: the first message deletes the locker row; a keep clause naming a row by a
   word that is a function word in another language (`Forget 4242 except the den.`) still keeps
   that row.
2. Leave the function words of the reading language out of the keep words, as `_whole` does.
3. Replay every string literal of the brain's forget tests through the card before and after, and
   count rows newly deleted: each must be one the message asks to delete.

## History

- 2026-11-15: filed while closing
  [task 1183](1183-a-forget-of-every-value-except-one-kind-keeps-a-row-of-another-kind.md).
