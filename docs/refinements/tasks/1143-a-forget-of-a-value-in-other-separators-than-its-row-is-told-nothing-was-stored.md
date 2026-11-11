# A forget of a value in other separators than its row is told nothing was stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-11

`ForgetChosenTool._choose` (`memory_forget_chosen.py`) returns `NONE_FOUND` whenever `find_text`
matches no row literally, before the rows `_repeating` found by the value are read. A row holding
the same value in other separators then gets no card, and the model reads "no remembered exchange
contains that text, so tell the user that nothing about it was stored". `UNMATCHED_FORGET_NOTE`
follows the reply, so the person is told an exchange in other words may still be stored, but the
reply the model writes says the fact was never stored.

Reproduction, unit level (`SCRATCH/slot13/sep.py`): the row "Remember that my phone account is 015
123 456 7890." and the message "Forget my phone account 015-123-456-7890.". A call with
`015-123-456-7890` (the message's own form) or `0151234567890` gets no card and `NONE_FOUND`, and
the row stays. A call with `015 123 456 7890` lists the row and deletes it.

Listing such a row is not a one-line change: letting `_repeating`'s rows through when the call's
text is only a value lists them, and fails
`test_a_value_named_in_other_groups_than_every_row_matches_nothing`
(`test_forget_value_separators.py`), which asserts that `0151 2345 6789` against a row holding
`015 123 456 789` matches nothing.

## What to do

1. Decide whether a literal miss with rows holding the value whole lists them on a card, or returns
   a result that says those rows hold the value in other separators and were kept. Neither may
   suggest a further forget.
2. Write the reproduction above and the groups test as one table of cases before the code.
3. Draw the neighbouring flows (a value named alone, forget what was just said) after the change.

## History

- 2026-11-11: filed by the second audit of the night; reproduced at unit level, no turn sent.
