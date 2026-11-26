# The lead words of a forget clause are not read from the table of forms

**Status:** declined 2026-11-26
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`forget_clauses.py` builds ten word sets from the table of forms (`forget_forms.py`). Three sets
still hold a copy of words the table holds: `_LEAD` the six words for but and `and`, `und` and
`et`; `_WHICH` the words `that` and `which`; `_NAMING` the words `the` and `my`. `JOIN`, the
words for and that join the rows a clause adds, is `_LIST & _LEAD`, so it holds no Spanish or
Romanian word for and (`y`, `și`), and the table shows no empty cell for it, since its row for
and also holds the words for or. Nothing lists a wrong row today: `_adds` (`forget_remarks.py`)
reads `JOIN` only beside an adding word, and no adding word is read in Spanish or Romanian.

## What to do

1. Split the row for and of the table into a row for and and a row for or, and build `_LIST`,
   `JOIN` and the words for and of `_LEAD` from them.
2. Build the words for but of `_LEAD` from the row for but, and give `UNREAD` a reason for each
   cell the split leaves empty.
3. Compare every word set of `forget_clauses.py` before and after: only `JOIN` and `_LEAD` may
   gain a word, and each word gained is replayed as a filled cell is.

## History

- 2026-11-15: filed from the audit of the table of forms, whose sets were compared with those
  of the commit before it: the same but for `toute`, `jede`, `jeden` and `jedes`.
- 2026-11-26: declined at the freeze of the forget message readers ([ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md) decision 7): no `FORMS` cell is filled any more, so its trigger cannot fire. The form lists and keeps no row today ([readings](../../readings/forget-freeze.md#forms-left-unread-at-the-freeze-2026-11-26)).
