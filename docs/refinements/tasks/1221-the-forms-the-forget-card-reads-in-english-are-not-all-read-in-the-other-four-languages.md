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
| a word for all | ro | `toate` | filled, 26 rows the message says stay are listed, each named with its article |
| a word for all | ro | `tot` | also means still, and is the Dutch word for until |
| a word for all | es | `todos`, `toda`, `todo` | Portuguese words too: `Esqueça todos os 4242.` then lists every row |
| a word for all | de | `alles` | a Dutch word too: `Verwijder alles, de card ook.` then lists two rows |
| a word for only | fr | `seulement` | filled, 272 rows not asked for are listed, none the message keeps |
| a word for only | de | `nur` | filled, 96 rows not asked for are listed |
| a word for only | es | `solo` | also means alone, and is an Italian word too |
| a word for only | ro | `doar` | filled, 8 rows the message says stay and 18 not asked for are listed |
| an adding word | es | `también` | filled, 14 rows not asked for are listed, none the message keeps |
| an adding word | ro | `de asemenea` | two words, and `și` is the word for and |
| a word for the or my | es | `el`, `los`, `mi`, `mis` | add a row only beside an adding word |

So `Oublie tous les 4242, seulement la carte.`, `Vergiss alle 4242, nur die Karte.`, `Olvida todas
las 4242, solo la tarjeta.` and `Uită toate 4242, doar cardul.` keep every row, where `Forget all
4242, only the card.` deletes the card. `Uită toate 4242.` keeps every row. Of 1,604 generated
messages of at most one clause, 602 keep a row the message asks to delete. A forget of everything
no longer lists a row its message says stays, which was what the four counted cells waited for;
the counts of those four cells are from the replay after it
([readings](../../readings/forget-everything-unread-role.md#the-four-blocked-cells-replayed-2026-11-15)).

## What to do

1. `toate`: a row named with the Romanian article (`dulapul` for a row holding `dulap`) names no
   row, so `Uită toate 4242, dulapul rămâne.` lists the locker code once `toate` is read. Fix
   that naming first (task 1217), then replay and fill the cell.
2. `seulement`, `nur` and `doar`: the rows not asked for are in forms where another clause adds
   or keeps a row, the largest `Oublie tous les 4242, la carte aussi, seulement le téléphone.`
   English `only` does the same today: `Forget all 4242, the card too, only the phone.` deletes
   the card and the locker code and keeps the phone. Fix that reading first, in every language.
3. `también` lists a row not asked for only beside `solo`, as in `Olvida 4242, el teléfono
   también, solo la tarjeta.`, so it waits for `solo`.
4. A word another language shares (`todos`, `alles`, `solo`, `tot`) needs a set read only in a
   message read as its language (`readings` in `forget_languages.py`), not a wider flat set.
   Filled, `doar` changes the Polish `Zapomnij 4242, doar card.`.
5. The replay scripts are `gen.py`, `run.py`, `newly.py` and `oneclause2.py` in
   `/home/david/.cache/cortex-run/2026-11-15/slot7/`, and `variant.py`, `variant.sh` and
   `analyze.sh` in `/home/david/.cache/cortex-run/2026-11-15/slot13/`.

## History

- 2026-11-15: filed from the generated messages of at most one clause
  ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
- 2026-11-15: a call text holding no digit now keeps each row no word of the message names when
  another stored row is named, so `Uită toate, cardul de asemenea.` with the call text `phone`
  keeps a phone it deleted before: 298 such rows in the generated messages
  ([readings](../../readings/forget-everything-but-call.md#a-call-naming-a-row-the-message-does-not-name-2026-11-15)).
- 2026-11-15: a forget of everything now keeps every row once it names one in a role no reader
  reads ([readings](../../readings/forget-everything-unread-role.md)), which the four cells
  waited for; replayed after it, none of the four is filled, for the rows in the table above; the
  forms it does not take as one are task
  [1230](1230-a-forget-of-everything-in-a-form-the-card-does-not-take-as-one-lists-a-row-its-message-keeps.md).
