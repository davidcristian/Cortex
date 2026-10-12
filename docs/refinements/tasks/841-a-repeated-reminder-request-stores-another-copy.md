# A repeated reminder request stores another copy

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-10-12

`ScheduleTaskTool.invoke` (`cortex_core/schedule_tools.py`) adds an item whatever the schedule
already holds, so a person who asks twice for the same reminder gets two items and two toasts at
the due time. In row B2 of [reminder-already-stored.md](../../readings/reminder-already-stored.md)
each of the 46 chats that called `schedule_task` stored another copy of a reminder the schedule
already held three or five times, and in one seeding chat the cortex cancelled seven of nine
copies that nobody named ([R-837](837-a-cancel-of-a-scheduled-item-needs-no-confirmation.md)).

A duplicate check was built and drawn as part of the result texts of
[R-839](839-a-reply-says-it-set-a-reminder-it-only-found-listed.md), described as the first part
of change T in the readings: before adding, `schedule_task` looks for an active item with the same
kind, text (case, spacing and a final full stop aside), due time, recurrence and model, never
letting a tainted item stand in for a clean request, and when it finds one it adds nothing and
returns `already scheduled` with that item's id. In rows T and T2 it found the stored item in all
91 calls and added nothing, a new request was still stored (rows E and E2), and a listing request
called nothing else (row Q2). It did not ship, because the rule those rows were drawn under
measured the false claim, which it did not change.

## What to do

Decide whether a repeat should add nothing, which fields make two requests the same, what the
result says, and whether a repeat on a full schedule still returns the stored item. Write the
decision into ADR-0025, then build it with a contract test per field, as the readings describe.

## History

- 2026-10-12: filed from the R-839 rows.
