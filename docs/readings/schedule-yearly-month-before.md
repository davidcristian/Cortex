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
B03 draws that stored 01-01, the birthday itself, are another wrong date, with rows of their own
below.

## Rows for the date itself, written before the candidate run, 2026-11-06

Two of fifteen B03 draws above stored a yearly rule on 01-01, the birthday itself, one of them
beside the right 12-31. The rows below score a day-before request by whether any stored `on_dates`
entry equals the named date: **on the date** when one does, **right** when the one stored entry is
the wanted date, **other** for the rest. B03 is drawn again with two more day-before requests whose
named date is the first of a month, so the day before falls in the month before.

| Row | Request | Wanted MM-DD | The date itself |
| --- | --- | --- | --- |
| B03 | "Note that my mother's birthday is on 1 January, and remind me the day before." | 12-31 | 01-01 |
| D01 | "My wife's birthday is on 1 July; remind me the day before." | 06-30 | 07-01 |
| D02 | "Note that our lease renews every year on 1 October, remind me the day before." | 09-30 | 10-01 |

The rule: the typed check ships for this defect only when **0 of the B03, D01 and D02 draws**
store the date itself and the count of right draws does not fall below the baseline's share (3 of
7 B03 draws). The check itself reads any stored `on_dates` entry other than the wanted one, which
covers the date itself, the refused month day in the named month and any third date alike, so one
check answers both rules. Its draws are capped by the slot's time box, three per request.

## The typed check on a candidate brain, 2026-11-06

`schedule_offset.py` reads one yearly date (the reader of `schedule_yearly.py`) and one offset
before it ("N days before", "a week before", "the day before") from the message, computes the
wanted MM-DD in a common and a leap year, and refuses once per turn a `schedule_task` call whose
`on_dates` holds any other date, with a result that names the wanted date; the next such call runs.
Of the 38 quoted messages in this file, `schedule-yearly-dates.md` and `schedule-yearly-ordinals.md`,
it reads eight as offset requests: the six rows here, the Y02 anniversary and the birthday and
renewal rows of the yearly readings. It leaves "The lease ends Sept. 30, remind me a week before"
(no yearly event word) and the two-birthday message (two dates) to run unchecked.

Candidate built from the working tree, the rig above, four draws per request from 03:49 to 03:59
UTC, the SM clock at 0.57 of its maximum on every row. Run log `rows-cand.jsonl`, `records-cand.jsonl`,
`rows-cand.clock` and the brain log `cand-calls.log` in slot 7 of the run's scratch directory. No
turn failed, every draw stored one item, and no `cortex:schedule*` key was left.

| Row | Right | Wrong month | On the date | Other | Refused first | Refused by the check |
| --- | --- | --- | --- | --- | --- | --- |
| B01 anniversary, a week before 3 September | 3 | 0 | 0 | 1 one-time 2027-08-27 | 1 of 4 | 0 |
| B02 renewal, two days before 1 March | 4 (1 on 02-27, 3 on 02-28) | 0 | 0 | 0 | 4 of 4 | 1 |
| B03 birthday, the day before 1 January | 4 | 0 | 0 | 0 | 3 of 4 | 0 |
| B rows together | 11 of 12 | 0 of 12 | 0 of 12 | 1 of 12 | 8 of 12 | 1 |
| N01 anniversary, a week before 20 May | 4 | 0 | 0 | 0 | 1 of 4 | 0 |
| D01 birthday, the day before 1 July | 4 | 0 | 0 | 0 | 2 of 4 | 0 |
| D02 lease, the day before 1 October | 4 | 0 | 0 | 0 | 2 of 4 | 0 |

Both rules pass: 0 of 12 B draws stored a wrong month against 2 of 22 in the row before, the right
B draws held at 11 of 12, all 4 N01 draws stored 05-13, and 0 of the 12 B03, D01 and D02 draws
stored the date itself against 2 of 15 before. The check fired once, on a B02 retry that stored
02-26 (two days before the refused 28) after the yearly refusal; its result named 02-27 or 02-28
and the third call stored 02-28. The check ships.

## A combined turn on the stack brain, 2026-11-06

The closing audit sent "My sister's birthday is 14 February, remind me three days before" to the
stack brain at 05:05 UTC (SM clock at 0.57 of its maximum). One `schedule_task` call,
`at: 2027-02-11T09:00:00Z`, no `on_dates`: the date is right, the time is the default, and the
reply, which named the date and no time, got the appended note "at 09:00". The reminder is a one-time
item, so it does not repeat with the birthday, and the offset check reads `on_dates` only: a one-time
`at` on the wrong date would have run. Rows `rows.jsonl`, `records.jsonl` and `rows.clock` in slot
11 of the run's scratch directory; the record was deleted after the read.

## A one-time reminder before a yearly date, written before the candidate run, 2026-11-06

The check now reads a one-time `at` the same way as `on_dates`: when the message names a yearly date
with an offset before it and the call's `at` (an ISO-8601 date-time) falls on a MM-DD other than the
wanted one, the call is refused once per turn with the result above, and a one-time `at` on the
wanted date runs, since the person may want this year's reminder only. An `at` that is not a
date-time (a time of day alone, a number) and a call with `in_seconds` are not read, so a call the
reader cannot place keeps its tool. Whether a one-time store for a yearly event should itself get a
note is a separate question and not part of this change. Every stored item recorded in this file
and in the closing audit's turn was a one-time `at` on the wanted date (2027-08-27, 2027-05-13,
2027-02-11), so no recorded draw would have been refused.

The rows: B01 above and the audit's turn A1, "My sister's birthday is 14 February, remind me three
days before", two draws each on a candidate built from the working tree. The rule: the check ships
on its tests and the replay of the recorded messages, which it does not change; the draws record
the stored item's shape (one-time `at` or a yearly rule) and its MM-DD, and whether the check fired.
A stored item on a date other than the wanted one, one-time or yearly, after the check files a
task; four draws decide nothing about how often the model stores a one-time item.

## The one-time check on a candidate brain, 2026-11-06

Candidate built from the working tree, two draws per row from 05:18 to 05:20 UTC, the SM clock at
0.57 of its maximum on three draws and 0.52 on the last. Run log `rows-cand.jsonl`,
`records-cand.jsonl`, `rows-cand.clock` and the brain log `cand-calls.log` in slot 12 of the run's
scratch directory. No turn failed, every draw stored one item, and no `cortex:schedule*` key was
left. The reader of the message, `wanted_dates`, is unchanged, so the replay above holds.

| Row | Draw | Stored | First call refused | Refused by the check |
| --- | --- | --- | --- | --- |
| B01 anniversary, a week before 3 September | 1 | one-time 2027-08-27 | no | no |
| B01 | 2 | yearly 08-27 | no | no |
| A1 birthday, three days before 14 February | 1 | yearly 02-11 | yes, monthly on the 11th | no |
| A1 | 2 | yearly 02-11 | yes, monthly on the 11th | no |

All four stored items fall on the wanted date, so the check had nothing to refuse, and the one-time
item ran as the rule says. Both A1 draws first called a monthly rule on the 11th, which the yearly
check refused, and the retry stored the yearly rule. Every reply names the date, and the first B01
reply, which named no time, got the appended time note. No task is filed from these draws.

## The second audit's combined turn on the stack brain, 2026-11-06

The second audit sent A1 again to the stack brain built from the one-time check, at 05:29 UTC (SM
clock at 0.57 of its maximum). One `schedule_task` call, not refused, stored the yearly rule
`hour 9, minute 0, year_dates [[2, 11]]`, due 2027-02-11T09:00 UTC; the reply named February 11th
and 9:00 AM, so no note was appended. The check fired 0 times. The refusal text a one-time `at`
would read still names `on_dates` and `at_time` (task 994). Rows `rows.jsonl`, `records.jsonl`
and `rows.clock` in slot 13 of the run's scratch directory; the record was deleted after the read.
