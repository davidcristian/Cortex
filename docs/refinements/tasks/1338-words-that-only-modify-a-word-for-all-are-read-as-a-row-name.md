# Words that only modify a word for all are read as a row name

**Status:** declined 2026-11-26
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`quantifies` (`forget_unnamed.py`) reads every word of the message that can name a row, less
the function words, as a row name, so a word the store holds no row for stops a word for all
and the message keeps every row. `other` and `single` are such words, so `Forget every other
4242.` and `Forget every single 4242.` keep every row they ask to delete: 498 rows of the
generated messages in `~/.cache/cortex-run/2026-11-24/f7/f3gen/`, 249 under each, and 46 more
in the literal calls over the brain's forget tests
([readings](../../readings/forget-everything-unread-role.md#a-word-of-the-message-no-stored-row-holds-2026-11-25)).
This is the safe direction: the card keeps rows.

## What to do

1. Add a row of the table of forms (`forget_forms.py`) for the words that only modify a word
   for all, and leave its words out of `named` in `quantifies` as the function words are. The
   words are the user's pick. Proposed cells, each with the reason for what it leaves out:
   - English: `other single`. The generator needs both.
   - French: `autre autres`. `seul` also means alone, so it can be part of a row's name.
   - German: `andere anderen anderes einzelne einzelnen`, for `alle anderen` and `jeden
     einzelnen`.
   - Spanish: `otros otras demás`, for `todos los demás`.
   - Romanian: empty, since the row for all has no Romanian word for it to modify.
   An alternative is the English cell alone, which removes the whole generated cost, since the
   generator writes `other` and `single` in every language.
2. Write the near misses first: `every other 4242` and `every single 4242` list every row
   holding the value, and `all cupboards 4242` keeps every row.
3. Replay the generator, the forget of everything cases, the mixed messages, the word pairs and
   the negations at the trees before and after: rows newly listed must be zero, and the 498
   rows asked to delete must be listed again.

## History

- 2026-11-25: filed from the close of
  [R-1265](1265-a-word-no-stored-row-holds-after-a-word-for-all-lists-every-row-holding-the-value.md),
  which reads the message's own words as row names in `quantifies` at the cost of these rows.
- 2026-11-26: declined at the freeze of the forget message readers ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7): its remedy adds a row of words to `FORMS`, so the freeze answers the pick it waited on, and its counts are over generated messages. 498 generated rows and 46 over the brain's forget tests stay kept ([readings](../../readings/forget-freeze.md#forms-left-unread-at-the-freeze-2026-11-26)).
