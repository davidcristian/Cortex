# A German article in a keep clause keeps every row holding it

**Status:** declined 2026-11-24
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

Over the rows `Merke dir, der Code vom Spind ist 4242.`, `Merke dir, meine Karte ist 4111 1111 1111
4242.` and `Merke dir, mein Handy ist 0721 555 4242.`, with the call text `4242`, the message
`Vergiss alle 4242 außer der Karte.` keeps all three rows, while `Vergiss alle 4242, behalte die
Karte.` deletes the locker row. `_split` (`forget_unnamed.py`) leaves no function word of the
reading language out of the words of a keep clause, so `der` is a keep word, and `names` finds it
in the locker row's text. This keeps a row, the safe direction, and the kept note shows it.

Leaving every function word of the reading language out of the keep words deletes a row the
message asks to keep. With a fourth row `Recuerda que el código del sobre es 4242.` beside the
Spanish rows of the same three facts, `Olvida todas las 4242 excepto el sobre y la tarjeta.`
keeps the `sobre` and card rows, and with `_words(keep, function)` in `_split` it deletes the
`sobre` row, since `sobre` is also a Spanish function word.

## What to do

1. Write tests first: the first message deletes the locker row; a keep clause naming a row by a
   word that is a function word in another language (`Forget 4242 except the den.`) still keeps
   that row, and the Spanish message above still keeps the `sobre` row.
2. Leave out of the keep words only a function word of the reading language directly before a
   word of the keep clause that names a row, as `der` before `Karte`, or decline the task, since
   the row is kept and shown.
3. Replay every string literal of the brain's forget tests through the card before and after, and
   count rows newly deleted: each must be one the message asks to delete.

## History

- 2026-11-15: filed while closing
  [task 1183](1183-a-forget-of-every-value-except-one-kind-keeps-a-row-of-another-kind.md).
- 2026-11-24: declined. The first message still keeps all three rows, and the kept note shows them.
  Step 2's rule was replayed over the forget card generator with this task's forms added (the run is
  in `~/.cache/cortex-run/2026-11-24/f1/`, `x1206.diff`): it deleted 209 more rows the message asks
  to delete and none it asks to keep, and kept the `sobre` and `den` rows (of the test literals it
  changed only `Vergiss alle außer der Karte.`, whose `Spind` row it deleted), but it also deleted
  48 rows the message does not ask for, the `Spind` row of `Vergiss 4242 außer der Karte nur auf dem
  Handy.` and forms like it, which the article had kept. So the cost stays: 209 generated rows asked
  to delete are kept.
