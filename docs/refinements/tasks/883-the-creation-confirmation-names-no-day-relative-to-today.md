# The creation confirmation names no day relative to today

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-10-16

`_confirmation` in `cortex_core/schedule_tools.py` writes the due time as a bare date-time, such as
`due 2026-10-25T09:00:00+01:00`, while a `list_scheduled` line adds its day counted from today
(`relative_day` in `schedule_render.py`), such as `(tomorrow)`. Near midnight the model then names
the wrong day in its reply. Asked "Remind me today at 9 to call the plumber." at 23:50 on
2026-10-24, one draw stored a rule due 09:00 on 10-25 and replied "today at 9:00 AM"
([readings](../../readings/schedule-time-edges.md#t5-results)).

## Reproduction

`slot8/draw.py F:10` in the 2026-10-16 run's scratch directory, against the cortex server at
127.0.0.1:8080: read the reply of each draw beside the confirmation in its trace.

## What to do

Add the relative day to the creation confirmation, as the listing writes it, so both read alike.
Write rows first: the readings' rows A and F, and E at 03:00 under the UTC zone, 10 draws each,
counting replies that name a day other than the stored one. It ships only if that count falls and
every draw still stores the instant it stored before.

## History

- 2026-10-16: filed from the T5 draws of the past time refusal and the daily repeat note.
