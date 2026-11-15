# A forget of everything deletes a row its message keeps in a form no reader reads

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

Over the rows `Remember that my locker code is 4242.`, `Remember that my card is 4111 1111 1111
4242.` and `Remember that my phone is 0721 555 4242.`, a message holding no value keeps a row in a
form the card does not read, and a call naming that row deletes it:

| Message | Call text | Deleted |
| --- | --- | --- |
| `Forget everything, the card stays, the phone too.` | `card` | the card |
| `Forget everything, the card stays, only the card.` | `card` or `4242` | the card |
| `Forget everything apart from the card.` | `card` or `4242` | the card |
| `Vergiss alles bis auf die Karte.` | `Karte` or `4242` | the card |
| `Uită toate în afară de card.` | `cardul` or `4242` | the card |

The same messages holding the value (`Forget all 4242, card stays.`) keep the card, because a row
named after the value under an unread role is kept (`beside` in `forget_clauses.py`). A message
without the value has no such run, so the words naming the card are read as asking to forget it.
A verb for stays is read as a keep verb in German only (`bleib` in `KEEP`): `stays`, `reste`,
`se queda` and `rămâne` are unread.

This blocks four cells of the table of forms (`forget_forms.py`): filled, `seulement`, `también`,
`doar` and `toate` each list a row the message says stays, 92 rows over 83 generated messages
([readings](../../readings/forget-everything-but-call.md#the-words-read-for-a-form-by-language-2026-11-15)).

## What to do

1. Write near misses first: `Forget everything about my stay.`, `Forget the card that stays in
   my wallet.`, `Forget what stays the same.` must list what they list today.
2. Change the shape, not the word list: a row named in a clause after a forget of everything,
   under a word no reader reads, is kept, as a row named after the value is.
3. Replay the pools and the generator of the readings section above: no row newly listed, and
   the rows newly kept counted by what the message asks.

## History

- 2026-11-15: filed from the replay of the translated cells of the table of forms, with task
  [1221](1221-the-forms-the-forget-card-reads-in-english-are-not-all-read-in-the-other-four-languages.md).
