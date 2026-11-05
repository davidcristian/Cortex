# Readings: a reminder before a yearly date in schedule_task

Whether the cortex stores a reminder before a yearly date (a birthday, an anniversary, a renewal)
as a yearly rule, through `at_time` with `on_dates`, or as a monthly rule (`on_month_days`), a
one-time reminder (`at`) or an interval (`every_seconds`). Read with
[ADR-0025](../adr/ADR-0025-scheduling-reminders.md); the tool is
`brain/packages/core/src/cortex_core/schedule_tools.py`, and the day selectors are in
`schedule_day_args.py`. The task is
[R-951](../refinements/tasks/951-a-reminder-the-day-before-a-yearly-date-can-repeat-monthly.md).

## The rig

**2026-11-05**, the GPU stack with the resident cortex (gemma-4-12B), both CPU subagent servers,
the filesystem sidecar and the pgvector memory override, with `CORTEX_SCHEDULE_BACKEND=redis` and
`CORTEX_SCHEDULE_TZ=UTC`, the brain built from `d74b637aa`. Each draw is one fresh chat over
`Converse`, with every card approved. After the turn the driver reads every `cortex:schedule:*`
record from Redis, then deletes the records and the `cortex:schedules:*` sets, so each draw starts
with no schedule. The current date during the draws is 2026-11-05.

## Rows and the rule, written before the first run

| Row | Request | Draws | Stored as wanted |
| --- | --- | --- | --- |
| Y01 | "Note that my mother's birthday is on 12 May, and remind me of it the day before." | 5 | yearly on 05-11 |
| Y02 | "Our wedding anniversary is on 3 September. Remind me a week before." | 5 | yearly on 08-27 |
| Y03 | "My car insurance renews every year on 20 March; remind me the day before." | 5 | yearly on 03-19 |
| M01 | "Remind me on the 11th of every month to pay rent." | 2 | monthly on day 11 |
| M02 | "Every month on the 25th, remind me to check my bank statement." | 2 | monthly on day 25 |

Each Y draw is counted as yearly, monthly, one-time, interval or nothing stored. The M rows are
near misses that really are monthly: they fix the baseline any typed check of the message must
keep.

The rule:

1. Monthly reminders recur when **2 or more of the 15 Y draws** store a monthly rule. A null
   result is 0 or 1 of 15, which leaves the tool alone and corrects the task with the counts.
2. When they recur, the next step is a typed check rather than a description sentence. A
   candidate ships only when, on the same rows, **0 of 15 Y draws** store a monthly rule, the
   count of yearly Y draws does not fall, and **all 4 M draws** still store a monthly rule.
3. A one-time reminder for the next occurrence is counted and reported, and decides nothing: "the
   day before" does not say every year, so it is a reading the request allows.

## Baseline, 2026-11-05

Drawn from 03:43 to 03:55 UTC, the SM clock at 0.51 to 0.52 of its maximum on every row. Run log
`rows.jsonl` and the stored records `records.jsonl` in slot 8 of the run's scratch directory. No
turn failed, every draw stored one item, and no `cortex:schedule*` key was left after the run.

| Row | Yearly | Monthly | One-time |
| --- | --- | --- | --- |
| Y01 birthday, the day before | 3 | 2 | 0 |
| Y02 anniversary, a week before | 3 | 1 | 1 |
| Y03 renewal, the day before | 3 | 2 | 0 |
| Y rows together | 9 of 15 | 5 of 15 | 1 of 15 |
| M01 and M02, monthly near misses | 0 | 4 of 4 | 0 |

Item 1 of the rule fired: 5 of 15 Y draws stored a monthly rule, on the day of the month the
yearly date falls on (11, 27, 19). The one-time Y02 draw stored 27 August 2027 at 09:00.

Three of the five monthly replies say "every month". The two monthly Y03 draws do not: their
replies say "every year on March 19th" and "on March 19th of every year at 9:00 AM" while the
stored rule fires on the 19th of every month, so the reply alone does not show the person what
was stored ([R-980](../refinements/tasks/980-a-reply-can-call-a-monthly-reminder-yearly.md)).
