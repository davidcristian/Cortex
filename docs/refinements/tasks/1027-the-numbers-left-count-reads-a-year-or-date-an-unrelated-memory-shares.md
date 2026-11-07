# The numbers left count reads a year or date an unrelated memory shares

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-07

`ForgetChosenTool._holding` counts every remaining row that holds any run of four or more digits a
deleted row held, from `digit_runs` over the whole row text, the assistant's words included. A year
or a date that two unrelated facts share is counted as the forgotten number still held. The result
then tells the model the number is still remembered, `NUMBERS_LEFT_NOTE` closes the reply, and the
note asks the person to forget the number itself, whose card would list the unrelated fact.

Reproduction, through `TurnEngine` with the fakes (`SCRATCH/slot20/probe_left.py`), every card
approved:

| Rows | Call | Reply | Note |
| --- | --- | --- | --- |
| "I got married in 2015", "I moved to Berlin in 2015" | `married` | "I've forgotten when you got married." | shown |
| dentist and gym reminders, each reply naming `2026-11-10` | `dentist` | "I've forgotten the dentist reminder." | shown |

In the second row the person never wrote the number: only the assistant's replies hold the date.

## What to do

1. Count the recorded forget flows in `docs/readings/forget-value-repeats.md` whose deleted rows
   hold a year or a date, and how many other stored rows share it.
2. Count only a run the person's own words in the deleted row hold, and a year only when the
   deleted row names it as a code (beside `code`, `PIN`, `number` or their translations); write
   the two rows above as near misses before the change, with the `1987` door code row kept.

## History

- 2026-11-07: filed by the third audit of the night's changes.
