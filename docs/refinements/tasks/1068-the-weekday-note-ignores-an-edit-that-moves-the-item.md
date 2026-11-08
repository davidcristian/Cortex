# The weekday note ignores an edit that moves the item

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-08

`weekday_off` in `schedule_weekday.py` reads only a `schedule_task` call that stored a one-time
item (`stores_once`), and `dispatch_round.py` keeps the last date it returned for the turn. Read
from the code on 2026-11-08, not drawn:

- An `edit_scheduled` call with `at` (which now moves a one-time item) a day off the one weekday
  the message names gets no `WEEKDAY_OFF_NOTE`.
- After a store a day off the weekday, a later call in the same turn that moves the item with `at`,
  makes it repeat with `at_time`, or cancels it leaves the note naming the old date, which is then
  false.

## What to do

1. Keep the item id beside the date, and drop or replace the date when a later call in the turn
   edits or cancels that id.
2. Read an `edit_scheduled` call with `at` as `weekday_off` reads a store.

## History

- 2026-11-08: filed by the audit of tonight's schedule changes, from the code.
