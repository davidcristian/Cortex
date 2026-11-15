# The forms the forget card reads in English are not all read in the other four languages

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15

The forget card reads a word for all, a limit, a keep clause opener and an adding form from word
sets in `forget_clauses.py`, each written as one flat set over five languages, so a language with
no word in a set is not visible. Of 42,356 generated messages, 1,604 hold at most one clause after
the value, and 602 of those keep a row the message asks to delete. That is the safe direction,
and part of it is by design in English too. The part that is a missing word, by the kind of
clause and the language, in cases keeping such a row:

| Clause | en | fr | de | es | ro |
| --- | --- | --- | --- | --- | --- |
| a word for only | 4 | 36 | 24 | 24 | 24 |
| an adding word | 12 | 9 | 9 | 27 | 28 |

The words the sets hold today, by form and language:

| Form | Set | en | fr | de | es | ro |
| --- | --- | --- | --- | --- | --- | --- |
| a word for all | `EVERY` | all, every, everywhere, everything | partout, tout, tous, toutes | überall, alle | todas | none |
| a limit | `_WHICH` | only, just | none | none | none | none |
| an adding word | `_ADD` | too, also, plus, as well | aussi, également | auch, ebenfalls | none | none |
| a word for except | `EXCEPT` | except, excluding | sauf, hormis, excepté | außer, ausgenommen | excepto, salvo | exceptând |
| but after a word for all | `_BUT` | but | none | none | none | none |
| a word for the or my | `_OWNER` | the, my | le, la, les, l, mon, ma, mes | der, die, das, den, mein, meine, meinen | in `_WHOSE` only | none |

So `Oublie tous les 4242, seulement la carte.`, `Vergiss alle 4242, nur die Karte.`, `Olvida todas
las 4242, solo la tarjeta.` and `Uită toate 4242, doar cardul.` keep every row, where `Forget all
4242, only the card.` deletes the card.

## What to do

1. Write the sets as one table in the code, a row for each form and a column for each of the
   five languages, and build each set from its row, so an empty cell is visible. Change no
   reader.
2. Fill only a cell that is the direct translation of a word English already reads (`seulement`,
   `nur`, `solo`, `doar` for only; `también` for too; `toate` for all). Add no form English does
   not read.
3. Write near misses first, and leave a cell empty when its word also means something else in
   that language: Romanian `și` is both and and also, Spanish `solo` is also alone, French
   `juste` is also right. Replay Italian, Portuguese, Dutch and Polish messages, which the card
   does not read and which share `solo`.
4. Replay the pool and the generator in `/home/david/.cache/cortex-run/2026-11-15/slot7/`
   (`gen.py`, `run.py`, `newly.py`, `oneclause2.py`): no row newly listed may be one the message
   asks to keep, each newly listed row must be one it asks to delete, and report the count of
   the 1,604 that still keep such a row.

## History

- 2026-11-15: filed from the generated messages of at most one clause
  ([readings](../../readings/forget-keep-except.md#the-role-of-a-row-named-after-the-value-2026-11-15)).
