# The numbers left count can miss a holder behind a common group

**Status:** done 2026-11-10
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`_holding` in `memory_forget_chosen.py` counts the rows left holding a deleted value by one
`find_text` per text of `value_searches`: the value as written, its letters and digits, and every
four consecutive characters of them. Each search returns at most `FORGET_CHOSEN_LIMIT + 1` rows,
and the filter after it keeps only rows whose digit runs hold the whole value. A row that restates
the value only in groups that are common elsewhere in the store ("06 1234 5678" after "0612345678",
with more than 20 other rows holding `1234` and `5678`) can be past the limit of every search
that reaches it. `numbers_left` is then `False` and `NUMBERS_LEFT_NOTE` does not show, the unsafe
side of a reply note. The card's `_repeating` uses the same searches, but there a missed row stays,
the safe side.

This is a reading of the code, not reproduced: no store tonight holds 20 rows sharing a group.

## What to do

1. When the trigger fires, reproduce it with `InMemoryMemoryStore` and 21 noise rows holding the
   group, then search the store once for every row holding any group and filter in the brain,
   or raise the limit for these searches alone.

## History

- 2026-11-08: filed by the night's audit slot, from a reading of `value_searches` and its callers.
- 2026-11-10: done with task 1042, before its trigger fired. `_holding` searches once per deleted
  digit run with `find_value`, so a row competes for the limit only when its text holds the whole
  run once separators are removed, not one group of it. A test with 25 rows holding `1234` and
  `5678` and a holder `06 1234 5678` failed before the change and passes after it.
