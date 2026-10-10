# A one-time reminder is stored as a daily one

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-10-10

Asked for something "tomorrow at 10:00", the cortex sometimes passes `at_time: "10:00"` to
`schedule_task`, and `at_time` is the recurring wall-clock argument: its description in
`schedule_tools.py` reads "Recurring wall-clock time ... Use this for 'every day at 9'". The item
is stored with a daily `rule` and is first due at the next 10:00, which can be the same day
([readings](../../readings/overlay-file-and-memory-flows.md#a-reminder-and-a-task-after-it)).

- After a refused task on a tainted turn, 2 of
  4 reminders made for "tomorrow at 10:00" between 06:54 and 06:58 UTC were stored with
  `rule: {"hour": 10, "minute": 0, "days": [0, 1, 2, 3, 4, 5, 6]}` and `due_at` 10:00 UTC the
  same day. Both replies said "tomorrow, October 11th, at 10:00 AM", against a creation result
  that names the due time and the daily repeat.
- In three more repeats of the task request, 2 of 3 refused calls passed `at_time: "10:00"` with
  `in_zone: "UTC"` for the same words, so the misuse is not specific to reminders.
- Untainted reminders asked for "tomorrow at 9:00" in the same run used `at` and were stored as
  one-shots on the right day.

## What to do

Decide whether the `at_time` description should say plainly that it makes the item repeat every
day, and that a one-time time goes in `at`. A change to a text the model reads is measured on the
cortex with rows written before the run: the "tomorrow at 10:00" reminder request, five repeats,
counting items stored with a `rule`.

## History

- 2026-10-10: filed from the file and memory flows on the Linux shell.
