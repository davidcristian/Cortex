# The lead words of a forget clause are not read from the table of forms

**Status:** open, waiting for its trigger
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-15
**Trigger:** an adding word is filled for Spanish or Romanian in the row `ALSO` of `FORMS` in
`forget_forms.py`. Recheck by reading that row: both cells empty means this has not fired.

`forget_clauses.py` builds ten word sets from the table of forms (`forget_forms.py`). Three sets
still hold a copy of words the table holds: `_LEAD` the six words for but and `and`, `und` and
`et`; `_WHICH` the words `that` and `which`; `_NAMING` the words `the` and `my`. `_JOIN`, the
words for and that join the rows a clause adds, is `_LIST & _LEAD`, so it holds no Spanish or
Romanian word for and (`y`, `și`), and the table shows no empty cell for it, since its row for
and also holds the words for or. Nothing lists a wrong row today: `_adds` reads `_JOIN` only
beside an adding word, and no adding word is read in Spanish or Romanian.

## What to do

1. Split the row for and of the table into a row for and and a row for or, and build `_LIST`,
   `_JOIN` and the words for and of `_LEAD` from them.
2. Build the words for but of `_LEAD` from the row for but, and give `UNREAD` a reason for each
   cell the split leaves empty.
3. Compare every word set of `forget_clauses.py` before and after: only `_JOIN` and `_LEAD` may
   gain a word, and each word gained is replayed as a filled cell is.

## History

- 2026-11-15: filed from the audit of the table of forms, whose sets were compared with those
  of the commit before it: the same but for `toute`, `jede`, `jeden` and `jedes`.
