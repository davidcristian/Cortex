# A one-time reminder on a named weekday can be stored a day late

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-08

On the stack brain on Sunday 2026-11-08 at 03:10, `Erinnere mich am Donnerstag um 7 Uhr an den
Arzttermin.` (chat `s4m-w4a`) made one `schedule_task` call with a one-time `at`, and the item was
stored for 2026-11-13 at 07:00 Berlin time, a Friday. The reply said "Donnerstag, den 13.
November", so the weekday is right and the date is the day after it. No refusal ran in that turn,
and the two baseline draws of the same message stored 2026-11-12. One draw, not replicated
([readings](../../readings/schedule-one-time-weekday.md)).

## What to do

1. Replicate first: draw the message and two other one-time weekday messages several times each
   and count items whose date is not the named weekday.
2. If it repeats, compare a typed check of the call against the message, in the shape of the
   date check beside a yearly date (`schedule_offset.py`): the weekday the message names against
   the weekday of the call's `at` date, refused once with the right date in the result.

## History

- 2026-11-08: filed by the slot that refused a weekly rule beside one named weekday, from a draw of
  its row W4.
