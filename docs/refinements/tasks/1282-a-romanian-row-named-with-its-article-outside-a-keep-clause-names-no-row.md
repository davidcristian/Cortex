# A Romanian row named with its article outside a keep clause names no row

**Status:** declined 2026-11-26
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

Over the rows `Ține minte că codul de la dulap este 4242.`, `Ține minte că cardul meu este 4111
1111 1111 4242.` and `Ține minte că telefonul meu este 0721 555 4242.`, with the call text `4242`,
`Uită dulapul 4242.` and `Uită 4242, păstrează dulapul.` keep all three rows: the first asks to
delete the locker, the second the card and the phone. The row holds `dulap`, the message says
`dulapul`, and `names` (`forget_kinds.py`) compares whole words, so every reader but `_restated`
(`forget_inside.py`, through `bare`) reads the message as naming no row. Each misread keeps the
rows and shows them, so no row is deleted against the message.

Reading the article `ul` in `names` for every reader was replayed on 2026-11-21 over the generator
of 42,356 messages: 764 changed, with 832 rows newly listed, 716 the message asks to delete, 90
either way and 23 it does not ask for, as the card of `Uită 4242, și cardul, doar dulapul.`, and
35 newly kept, 6 of them rows the message asks to delete. Of the strings of the brain's forget
tests, `Uită toate, cardul rămâne, dulapul rămâne.` with the call text `dulap` then lists the
locker it asks to keep, and `Uită cardul 4242 mai puțin codul de la sală.` lists the card:
`cardul` less its article is the row word `card`, which `names` then reads outside the words of
`read_kinds`. The listing is `cmp_p1a.txt` in `~/.cache/cortex-run/2026-11-21/f2/`.

## What to do

1. Write tests first: the two messages above delete the rows they ask for, and the three
   messages of the replay that listed a row against the message keep it.
2. Read the article reader by reader, never in `names` itself, and never for a word of the table
   of kinds. Replay each reader alone: a row newly listed must be one the message asks to delete.
3. Leave the forms `le`, `a` and `ua` unread: `Ioana` would name the row of `Ioan`.

## History

- 2026-11-21: filed with the change that reads the article in a keep clause naming the row to
  forget again
  ([R-1217](1217-a-romanian-row-named-with-its-article-in-a-keep-clause-names-no-row.md)).
- 2026-11-24: still open. In unit calls at the tree that reads a later clause in a message
  lacking the value, `Uită dulapul 4242.` and `Uită 4242, păstrează dulapul.` with the call text
  `4242` keep all three rows, and `Uită dulapul.` with the call text `dulap` deletes the locker.
- 2026-11-26: still open. `Uită dulapul 4242.` with the call text `4242` keeps the locker
  through the check in `kept_rows` (`forget_inside.py`) that keeps a row holding the value whole
  when no word of the message is a row word. Reading the article `ul` in that check alone
  deletes the locker and 49 rows asked to delete over the generator, but lists 6 rows not asked
  for over the word pairs, as a locker of another language holding `4242` for `Forget my
  dulapul 4242.`, and 10 generator rows marked neither way beside `all` or `everywhere`, so it
  was not built.
  `Uită 4242, păstrează dulapul.` keeps every row through `unnamed` (`forget_unnamed.py`). The
  replay is in `~/.cache/cortex-run/2026-11-26/f4/` (tree `c5`).
- 2026-11-26: declined at the freeze of the forget message readers ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7): its counts are over generated messages and its remedy reads a new word form. 716 rows asked to delete stay kept over 42,356 generator messages ([readings](../../readings/forget-freeze.md#forms-left-unread-at-the-freeze-2026-11-26)).
