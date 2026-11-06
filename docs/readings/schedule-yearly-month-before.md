# Readings: a reminder in the month before a yearly date

Whether the cortex stores a reminder that falls in the month before a yearly date (a week before
3 September is 27 August) on the right `on_dates` entry after the yearly date refusal
(`schedule_yearly.py`), or on the refused call's month day in the named date's month (09-27).
Read with [schedule-yearly-dates.md](schedule-yearly-dates.md), which has the rig, the refusal
and the draw that filed this: one of seven refused Y02 draws stored 09-27. The task is
[R-981](../refinements/tasks/981-a-refused-monthly-call-can-be-stored-on-the-wrong-month.md).

## What the code does

The retry after a `YEARLY_DATE` refusal runs when its `on_month_days` equal the refused call's
(`same_month_days`, `dispatch_round.py`); a call with `on_dates` is never read against the
message. Nothing typed checks the stored MM-DD. The refusal text names "a day of a named month"
and its example maps a date to itself (`'05-11'` for 11 May), so a reminder due in the month
before has no example to follow.

## Rows and the rule, written before the first run

| Row | Request | Draws | Wanted MM-DD |
| --- | --- | --- | --- |
| B01 | "Our wedding anniversary is on 3 September. Remind me a week before." | 4 | 08-27 |
| B02 | "My car insurance renews every year on 1 March; remind me two days before." | 4 | 02-27 (02-28 in a leap year) |
| B03 | "Note that my mother's birthday is on 1 January, and remind me the day before." | 4 | 12-31 |
| N01 | "Our wedding anniversary is on 20 May. Remind me a week before." | 4 | 05-13 |

A draw is scored by the stored rule's MM-DD against the wanted one: **right**, **wrong month**
(the day of the named date's month that the refused monthly call named, 09-27 for B01) or
**other** (any other date, a monthly rule, a one-time reminder, nothing stored). Whether the draw
was refused first is read from the brain log. N01 is the near miss whose reminder stays in the
named date's month: it fixes what a candidate must keep.

The rule:

1. The defect recurs when **1 or more of the 12 B draws** store a wrong month. A null result is 0
   of 12, which leaves the behaviour alone and adds draws in the next row rather than a change.
2. When it recurs, the first candidate is a typed check of the retry's `on_dates` entry: when the
   message names a yearly date and a relative offset before it, and the stored entry is the
   refused month day in the named date's month, the call is refused with the date the reminder
   should fire on. It ships only when, on the same rows, **0 of 12 B draws** store a wrong month,
   the count of right B draws does not fall, and **all 4 N01 draws** still store 05-13.
3. The second candidate, tried only if the first fails its counts, is a refusal text that names
   the date the reminder fires on rather than the named date, with the same counts.
4. A B01 draw that stores a one-time reminder for 27 August 2027 is counted as other and decides
   nothing, as in the yearly rows.

## Baseline, 2026-11-06

The stack brain built from `f3dbe7083` (the refusal, the narrowed reader and the stored-time note),
the rig of the yearly readings, drawn from 03:20 to 03:25 UTC, the SM clock at 0.56 to 0.57 of its
maximum on every row. Run log `rows-base.jsonl`, the stored records `records-base.jsonl` and the
brain log `base-calls.log` in slot 6 of the run's scratch directory. No turn failed, every draw
stored one item, and no `cortex:schedule*` key was left after the run.

| Row | Right | Wrong month | Other | Refused first |
| --- | --- | --- | --- | --- |
| B01 anniversary, a week before 3 September | 3 | 0 | 1 one-time 2027-08-27 | 0 |
| B02 renewal, two days before 1 March | 4 (3 on 02-27, 1 on 02-28) | 0 | 0 | 3 |
| B03 birthday, the day before 1 January | 4 | 0 | 0 | 0 |
| B rows together | 11 of 12 | 0 of 12 | 1 of 12 | 3 of 12 |
| N01 anniversary, a week before 20 May | 2 | 0 | 2 one-time 2027-05-13 | 2 of 4 |

A null result under item 1 of the rule: 0 of 12 B draws stored a wrong month, so the behaviour is
left alone. Each of the three refused B02 calls held `on_month_days` [28], the day in the month
before, and every retry stored it in February; the two refused N01 calls held [13] and their
retries stored 05-13 as a one-time reminder and as a yearly rule. Every reply names the stored
date.

The next row is the same four requests, eight draws each, before any change: the draw that filed
the task was 1 of 7 refused draws, and this run's 3 refused B draws cannot show a rate that low.

## The next row, 2026-11-06

Same brain, rows and driver, eight draws per request with a local deadline that cut the last
three (B01 8 draws, the other rows 7), drawn from 03:27 to 03:39 UTC while `just check` ran on the
host, the SM clock at 0.52 to 0.58 of its maximum. Run log `rows-base2.jsonl`, `records-base2.jsonl`
and the brain log `base2-calls.log` in slot 6. No turn failed, and no `cortex:schedule*` key was left.

| Row | Right | Wrong month | Other | Refused first |
| --- | --- | --- | --- | --- |
| B01 anniversary, a week before 3 September | 5 | 0 | 3 one-time 2027-08-27 | 3 of 8 |
| B02 renewal, two days before 1 March | 7 (3 on 02-27, 4 on 02-28) | 0 | 0 | 3 of 7 |
| B03 birthday, the day before 1 January | 3 | 2 | 1 on 01-01, 1 on both 12-31 and 01-01 | 3 of 7 |
| B rows together | 15 of 22 | 2 of 22 | 5 of 22 | 9 of 22 |
| N01 anniversary, a week before 20 May | 2 | 0 | 5 one-time 2027-05-13 | 0 of 7 |

The defect recurred: both wrong-month B03 draws were refused first with `on_month_days` [31] and
stored 01-31, the refused day in the birthday's month, as the draw that filed the task did. Over
both runs 2 of 34 B draws stored a wrong month, both among the 12 refused first, and no draw
that ran its first call did. Item 2 of the rule now applies: the next step is the typed check of
the retry's `on_dates` entry, with its near misses as tests first, drawn on these rows. The two
B03 draws that stored 01-01, the birthday itself, are another wrong date
([R-991](../refinements/tasks/991-a-day-before-reminder-can-be-stored-on-the-yearly-date-itself.md)).
