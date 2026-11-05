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
was stored.

## The yearly date refusal, 2026-11-05

The candidate is the brain built from the working tree with the refusal and before the reply note
below, which reads only the reply and stores nothing: the first
`schedule_task` call with `on_month_days` in a turn whose message `names_yearly_date` reads
(`schedule_yearly.py`: a day of a named month and no month word) is refused as `YEARLY_DATE`,
whose text gives the `on_dates` form. Same rows and driver, drawn from 04:03 to 04:17 UTC on a
second brain beside the stack's, the SM clock at 0.51 to 0.52 of its maximum on every row. Run log
`rows.jsonl`, `records.jsonl` and the brain log `cand.log` in slot 9 of the run's scratch directory.
No turn failed, every draw stored one item, and no `cortex:schedule*` key was left.

| Row | Yearly | Monthly | One-time | Refused first |
| --- | --- | --- | --- | --- |
| Y01 birthday, the day before | 5 | 0 | 0 | 2 |
| Y02 anniversary, a week before | 3 | 0 | 2 | 1 |
| Y03 renewal, the day before | 5 | 0 | 0 | 4 |
| Y rows together | 13 of 15 | 0 of 15 | 2 of 15 | 7 of 15 |
| M01 and M02, monthly near misses | 0 | 4 of 4 | 0 | 0 |

Item 2 of the rule passes: 0 of 15 Y draws stored a monthly rule, the yearly count rose from 9 to
13, and all 4 M draws stored a monthly rule. Every refused draw then stored a yearly rule, and no
draw made a second monthly call. One refused Y02 draw stored the yearly date 09-27, the day of the
refused call in the anniversary's month, where the request wanted 08-27; no baseline yearly draw
stored a wrong date
([R-981](../refinements/tasks/981-a-refused-monthly-call-can-be-stored-on-the-wrong-month.md)).

The reader replayed every quoted string in `docs/readings/`, the task files and the brain tests
(10,410 strings): 34 match, and none of them asks for a monthly reminder, since a string with a
month word never matches. The person's messages among them are the three Y requests, "Note that my
mother's birthday is on 12 May." (a request to remember, where `schedule_task` is refused as
unasked anyway) and "Remind me on 14 March 2027 at 10:00 to renew the passport." (a one-time
reminder, for which a monthly rule would be wrong). The rest are replies, test strings and the
documents of a live spawn test, which the reader never reads.

## The reply against the stored rule: rows and the rule, written before the R01 draws

The check is a note the brain appends: `schedule_claim.claims_yearly` reads a reply that names a
yearly repeat ("every year", "each year", "yearly", "annually", "once a year") and no month, and
the note is added when a `schedule_task` call in the turn stored `on_month_days`.

| Row | Request | Draws | Brain |
| --- | --- | --- | --- |
| R01 | Y03's request | 4 | the stack brain, which has no yearly date refusal |

The rule: the note ships when, over every draw in this record (the baseline, the candidate rows
below and R01), replayed through the reader with the record each draw stored, it is appended on
every draw that stored a monthly rule while the reply names a yearly repeat, and on no other draw.
A null result for R01 is no monthly draw, which tests nothing new and decides nothing.

## R01 and the replay, 2026-11-05

R01 drawn from 04:16 to 04:19 UTC on the stack brain, the SM clock at 0.51 to 0.52 of its maximum;
run log `r01/rows.jsonl` in slot 9 of the run's scratch directory, no turn failed and no
`cortex:schedule*` key was left. Three of four draws stored the 19th of every month, and all
three replies said "March 19th every year" or "every year on March 19th"; the fourth stored 03-19
yearly.

| Draws replayed | Monthly rule stored | Monthly with a yearly reply | Note appended |
| --- | --- | --- | --- |
| Baseline, 19 | 9 | 2 | 2 |
| Candidate, 19 | 4 | 0 | 0 |
| R01, 4 | 3 | 3 | 3 |

The rule passes: the note is appended on all 5 draws whose reply calls a stored monthly rule
yearly, and on none of the other 37 draws: 11 stored a monthly rule and the reply named no
yearly repeat or named a month, and 26 stored no monthly rule. Of the 10,423 quoted strings replayed through `claims_yearly`, 13 match;
the note needs a stored monthly rule as well, so none of them adds a note in a turn that stored
none.

## Monthly requests with a named date, 2026-11-05

Two real turns on the stack brain (the build with the refusal and the reply note), drawn from
04:26 to 04:29 UTC, the SM clock at 0.52 of its maximum at the start; brain log
`brain-calls.log` in slot 10 of the run's scratch directory. Each message asks for a monthly
reminder and names a start date with no month word.

| Message | First call | Refused | Stored |
| --- | --- | --- | --- |
| "Remind me to pay the gas bill on the 15th, starting 15 June." | `on_month_days` [15] | yes | `on_dates` ["06-15"], yearly |
| "Starting May 1, remind me on the 1st to pay rent." | `on_month_days` [1] | yes | `on_dates` ["05-01"], yearly |

Both replies said "every year". A third turn repeating the first message listed the stored
reminder and stored nothing. The draws' two records were deleted after the run, and no
`cortex:schedule*` key was left. The narrowed reader below answers these turns.

## The narrowed reader: rows and the rule, written before the N and T draws

The candidate reads a yearly date only when the message also names a yearly event ("birthday",
"anniversary", "renew", "annual", "yearly", "every year", "once a year"), and does not refuse a
monthly call on a day the message names as an ordinal with no month beside it ("on the 15th").
Each monthly call is refused once per set of month days, so a second date's call on other days is
refused too, and a retry on the same days runs. The candidate is the stack brain rebuilt from the
working tree; the driver is the one above.

| Row | Request | Draws | Stored as wanted |
| --- | --- | --- | --- |
| N01 | "Remind me to pay the gas bill on the 15th, starting 15 June." | 2 | monthly on day 15 |
| N02 | "Starting May 1, remind me on the 1st to pay rent." | 2 | monthly on day 1 |
| N03 | "Remind me of Anna's birthday on 11 May and to pay the gas bill on the 15th." | 1 | a monthly rule on day 15 |
| T01 | "Remind me of Anna's birthday on 11 May and of Tom's birthday on 3 June." | 1 | no monthly rule |

The rule: the candidate ships when all 4 N01 and N02 draws store a monthly rule and the N03 draw
stores one on day 15. T01 is one draw and decides nothing alone; a monthly rule there is filed.
The Y rows are not drawn again: their messages still match, the request the brain sends is
unchanged, and the change acts only on a second monthly call, which no Y draw made.

## The narrowed reader, 2026-11-05

Drawn from 04:39 to 04:46 UTC on the stack brain rebuilt from the working tree, the SM clock at
0.51 of its maximum on every row. Run log `rows.jsonl`, `records.jsonl` and `draw.log` in slot 11
of the run's scratch directory; no turn failed, and no `cortex:schedule*` key was left.

| Row | Calls in the brain log | Stored |
| --- | --- | --- |
| N01, 2 draws | `on_month_days` [15], ran | monthly on day 15, 2 of 2 |
| N02, 2 draws | `on_month_days` [1], ran (one draw first sent `at` with `at_time`, refused as invalid) | monthly on day 1, 2 of 2 |
| N03, 1 draw | two `at` calls | one-time on 2027-05-11 and 2027-05-15 |
| T01, 1 draw | `on_month_days` [11] and [3], both refused; then `on_dates` ["05-11"] and ["06-03"] | yearly on 05-11 and 06-03 |

All 4 N01 and N02 draws stored a monthly rule, where both turns of these messages on the first
build stored a yearly one. The N03 item is not met as written: the cortex made no monthly call, so the refusal
never acted, and the item measured a choice the change cannot reach; the unit tests hold the
day-15 call. In T01 the second date's monthly call was refused too, where the first build ran it.

The reader replayed every quoted string in `docs/readings/`, the task files and the brain tests,
plus the test file before the change (27,166 strings): the old reader matches 56, the new one 27,
and every new match is an old match. Of the 29 strings it no longer reads, six are requests with
no yearly event: both N01 and N02 messages, "From 3 March, remind me every 4 weeks to change the
water filter.", "I'm away until June 2, so remind me on the 5th to water the plants.", "remind me
on the 3rd of june about the dentist" and "The lease ends Sept. 30, remind me a week before.". A
first build refuses a monthly call on each of them. The other 23 are replies and document
passages, which the reader never reads. The three Y requests still match and name no bare day.

## Ordinal words, 2026-11-05

A second audit found that `bare_days` read only digit ordinals, so "Remind me of Anna's birthday
on 11 May and to pay rent on the first." had its monthly call on day 1 refused, with the `on_dates`
form as the fix the refusal names. The reader now also reads an ordinal word from "first" to
"thirty first" after "the" or "every", unless a month is beside it ("the first of June"). The
change only adds days, so it can only let a monthly call run. Replaying the quoted strings in
`docs/readings/`, the task files and the brain tests (12,536 strings, 34 read as a yearly date)
through both readers changes the days of four strings, all four added by this change's tests.
