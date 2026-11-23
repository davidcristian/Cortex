# A forget of a value with an added row keeps the other rows holding the value

**Status:** done 2026-11-23
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`Forget 4242, the card too.` asks for the value and adds the card. On 2026-11-15 a unit call
through `ForgetChosenTool` with the text `4242`, over a locker code `4242`, a card and a phone
that end in `4242`, deleted only the card and kept the locker code, which holds the value whole.
`Forget 4242.` alone deletes the locker code. Since the card lists a match of a call text holding
no digit only when the call by value lists it (`permitted` in `forget_permit.py`), the texts
`locker code` and `phone` keep their rows too.

In the replay of that change 2,953 rows the generator marks asked to delete were kept by the
call by value: 284 under a plain head with one or two added rows, 105 under a word for all with a
limit then an added row, 382 under an added row beside `stays`
([readings](../../readings/forget-everything-but-call.md#the-message-permits-and-the-call-selects-2026-11-15)).

## What to do

1. Check the premise first: read which reader keeps the locker code (`unnamed` in
   `forget_unnamed.py` keeps a row no word of the message names when a word names another).
2. Write the near misses as tests first: `Forget the card 4242, my phone as well.` deletes both
   and keeps the locker code, and `Forget 4242, the card stays.` keeps the card.
3. Read an addition after a value with no row named before it as adding to the rows holding the
   value whole, then replay the pools: each newly listed row must be one the message asks for.

## History

- 2026-11-15: filed from the replay of the rows a message permits.
- 2026-11-23: done. `unnamed` (`forget_unnamed.py`) kept the locker code: the card names a row,
  so each row holding the value that no word names was kept. A message that is a forget verb,
  the value, then only words adding a stored row now asks for every row holding the value whole
  (`adds_to_value` in `forget_value_added.py`), so `Forget 4242, the card too.` deletes the card
  and the locker code with the text `4242`, and the locker code with `locker code`. The phone
  `0721 555 4242` stays kept as for `Forget 4242.`, and the two near misses list what they did.
  Over both generators no row asked to keep was listed and 124 rows asked to delete were newly
  listed, with none the message does not ask for
  ([readings](../../readings/forget-value-added-row.md)).
