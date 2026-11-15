# The forms the forget card reads in English are not all read in the other four languages

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

The words the forget card reads for a form are one table (`forget_forms.py`): a row for each
form, a cell for each of English, French, German, Spanish and Romanian, and in `UNREAD` the reason
a cell is empty. These cells are empty, each with the count of its replay
([readings](../../readings/forget-everything-but-call.md#the-words-read-for-a-form-by-language-2026-11-15)):

| Form | Cell | Word | Why it is empty |
| --- | --- | --- | --- |
| a word for all | ro | `toate`, `toți`, `toată` | filled, 72 rows the message says stay are listed |
| a word for all | ro | `tot` | also means still, and is the Dutch word for until |
| a word for all | es | `todos`, `toda`, `todo` | Portuguese words too: `Esqueça todos os 4242.` then lists every row |
| a word for all | de | `alles` | a Dutch word too: `Verwijder alles, de card ook.` then lists two rows |
| a word for only | fr | `seulement` | filled, 6 rows the message says stay are listed |
| a word for only | de | `nur` | filled, 96 rows not asked for are listed |
| a word for only | es | `solo` | also means alone, and is an Italian word too |
| a word for only | ro | `doar` | filled, 24 rows the message says stay are listed |
| an adding word | es | `también` | filled, 12 rows the message says stay are listed |
| an adding word | ro | `de asemenea` | two words, and `și` is the word for and |
| a word for the or my | es | `el`, `los`, `mi`, `mis` | add a row only beside an adding word |

So `Oublie tous les 4242, seulement la carte.`, `Vergiss alle 4242, nur die Karte.`, `Olvida todas
las 4242, solo la tarjeta.` and `Uită toate 4242, doar cardul.` keep every row, where `Forget all
4242, only the card.` deletes the card. `Uită toate 4242.` keeps every row. Of 1,604 generated
messages of at most one clause, 602 keep a row the message asks to delete, and 505 with every
cell above filled.

## What to do

1. A forget of everything now keeps a row the message says stays, so replay `seulement`,
   `también`, `doar` and the Romanian words for all again and fill each cell whose replay lists
   no row the message keeps or does not ask for.
2. `nur`: the 96 rows are over 15 generated forms in which another clause adds or keeps a row,
   the largest `Vergiss alle 4242, die Karte auch, nur das Handy.` (24 rows, the locker code).
   English `only` does the same today: `Forget all 4242, the card too, only the phone.` deletes
   the card and the locker code and keeps the phone. Fix that reading first, in every language.
3. A word another language shares (`todos`, `alles`, `solo`, `tot`) needs a set read only in a
   message read as its language (`readings` in `forget_languages.py`), not a wider flat set.
4. Romanian names a row with the article as an ending (`dulapul` for a row holding `dulap`), so
   `exceptând dulapul` keeps no row. Replay that before filling a Romanian cell.
5. The replay scripts are `gen.py`, `run.py`, `newly.py` and `oneclause2.py` in
   `/home/david/.cache/cortex-run/2026-11-15/slot7/`.

## History

- 2026-11-15: filed from the generated messages of at most one clause
  ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
- 2026-11-15: a call text holding no digit now keeps each row no word of the message names when
  another stored row is named, so `Uită toate, cardul de asemenea.` with the call text `phone`
  keeps a phone it deleted before: 298 such rows in the generated messages
  ([readings](../../readings/forget-everything-but-call.md#a-call-naming-a-row-the-message-does-not-name-2026-11-15)).
- 2026-11-15: a forget of everything now keeps every row once it names one in a role no reader
  reads ([readings](../../readings/forget-everything-unread-role.md)), which the four cells
  waited for; the forms it does not take as one are task
  [1230](1230-a-forget-of-everything-in-a-form-the-card-does-not-take-as-one-lists-a-row-its-message-keeps.md).
