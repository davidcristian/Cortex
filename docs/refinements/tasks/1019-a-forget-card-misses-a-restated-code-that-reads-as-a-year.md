# A forget card misses a restated code that reads as a year

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

`forget_memories` lists, beside the rows holding the call's text, the rows that hold a whole value
of a match and a word of the text (`_repeating` in `memory_forget_chosen.py`). `whole_values` in
`memory_values.py` drops a run that reads as a year from 1900 to 2099 (`_dated`) and a run
followed by a unit word (`_UNIT_AFTER`), and that list includes the German preposition `am`. A
door code such as `1987`, a common choice since people pick birth years, and a code written
before `am` ("Der Code 4512 am Hintereingang") are therefore no value at all, so a row restating
them without the call's text is not listed and stays after the forget. The token reader before the
whole value reader listed both rows.

Reproduction, unit level (`SCRATCH/slot16/probe.py` beside the token reader of the parent commit):

| Rows | Call text | Token reader | Whole value reader |
| --- | --- | --- | --- |
| "my door code is 1987", "The code for the door is still 1987, right?" | `door code` | 2 rows | 1 row |
| "der Türcode ist 4512", "Der Code 4512 am Hintereingang, oder? ... der Türcode" | `Türcode ist` | 2 rows | 1 row |

## What to do

1. Write both rows above as tests in `test_forget_value_repeats.py` first, with near misses that
   must stay out: a year stated as a year ("born in 1987"), a price before `EUR`.
2. Read a year as a date only beside a date word or a day and month, and read `am` as a unit only
   after a clock time, never after a bare code. A reader that decides what a destructive card
   lists fails toward listing the row, since the person sees every row before the delete.

## History

- 2026-11-07: filed by the second audit of the night; reproduced at unit level, no turn sent.
- 2026-11-07: the card's listing stays as it is. The count of task 1003 reached both rows of the
  reproduction at unit level, since it compares every run of four or more digits, years alike,
  and it does not ship yet ([readings](../../readings/forget-value-repeats.md#the-draws-of-both-results-2026-11-07)), so this task follows task 1003.
