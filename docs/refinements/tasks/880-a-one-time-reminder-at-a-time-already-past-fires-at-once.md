# A one-time reminder at a time already past fires at once

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-10-16

`schedule_task` accepts an `at` that is not after now. `_parse_due_at` in
`cortex_core/schedule_args.py` checks only that `at` is an ISO-8601 date-time, so a past time is
stored, `claim_due` returns it on the ticker's next poll, and the reminder fires within seconds of
being made. The confirmation, `scheduled reminder <id>: due <time>`, has no relative day, so it
reads like any other and the reply tells the person the reminder is set for a time that has
passed. A wrong date from the model (a "tomorrow" read against the wrong day, R-881) turns into a
reminder that fires at once instead of a correction it could act on. Asked "Remind me today at 9
to call the plumber." at 23:50, the cortex wrote the past 09:00 in 1 of 10 draws
([readings](../../readings/schedule-time-edges.md#t2-one-time-times-in-the-repeated-hour-the-gap-and-the-past)).

## Reproduction

Under a fixed clock at 2026-10-24 23:50 CEST with a Berlin display zone, `parse_schedule` with
`{"kind": "reminder", "text": "check the oven", "at": "2026-10-24T09:00:00"}` stores 07:00 UTC,
the confirmation shows `due 2026-10-24T09:00:00+02:00`, and `InMemoryScheduleStore.claim_due`
returns the item 5 s later (`slot7/flow12.py`, row T2f, in the 2026-10-16 run's scratch directory).

## What to do

Refuse an `at` that is more than a small margin (60 s) before now, with a correction that names the
current date-time in the display zone, for example "'at' 2026-10-24T09:00:00+02:00 has passed; the
current date-time is 2026-10-24T23:50:00+02:00 (Europe/Berlin)". The margin keeps a call that
writes "now" itself from being refused. ADR-0065 notes that a refusal costs a round trip, so this
ships only on rows written first: the readings' rows A, D and F (F asks for "today at 9" at
23:50), with F drawn 20 times, under the rule that every A and D draw still stores its wanted instant with no extra
call, and the new row either asks or stores the next day, never a past time. Then edit ADR-0025's
creation bounds and the runbook.

## History

- 2026-10-16: filed from the time edge flows on the shared stack.
