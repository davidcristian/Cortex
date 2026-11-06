# Readings: an ordinal word beside a yearly date in schedule_task

How `bare_days` in `brain/packages/core/src/cortex_core/schedule_yearly.py` reads an ordinal word
("the first", "every twenty-first") beside a yearly date, and what that decides for a monthly
`schedule_task` call (`on_month_days`) in a turn whose message names a yearly date. The rig, the
driver, the yearly date refusal and the digit reader are in
[schedule-yearly-dates](schedule-yearly-dates.md); read with
[ADR-0025](../adr/ADR-0025-scheduling-reminders.md). The tasks are
[R-951](../refinements/tasks/951-a-reminder-the-day-before-a-yearly-date-can-repeat-monthly.md)
and
[R-989](../refinements/tasks/989-an-ordinal-word-that-is-not-a-day-lets-a-monthly-birthday-run.md).

## Ordinal words, 2026-11-05

A second audit found that `bare_days` read only digit ordinals, so "Remind me of Anna's birthday
on 11 May and to pay rent on the first." had its monthly call on day 1 refused, with the `on_dates`
form as the fix the refusal names. The reader now also reads an ordinal word from "first" to
"thirty first" after "the" or "every", unless a month is beside it ("the first of June"). The
change only adds days, so it can only let a monthly call run. Replaying the quoted strings in
`docs/readings/`, the task files and the brain tests (12,536 strings, 34 read as a yearly date)
through both readers changes the days of four strings, all four added by this change's tests.

## An ordinal word before a noun: rows and the rule, written before the change

The reader above reads an ordinal word after "the" or "every" as a month day also when a noun
follows it ("the first one", "every second year"). When that number equals the day of the named
date, a monthly call on that day is not refused, and the person gets a monthly rule for a birthday.
The rows, each a message with the monthly call the cortex may make from it:

| Row | Message | Monthly call | Wanted |
| --- | --- | --- | --- |
| O01 | "Remind me of Leo's birthday on 1 July, it's the first one he has at school" | `on_month_days` [1] | refused |
| O02 | "Remind me of Tom's birthday on 2 March, every second year we throw a party" | `on_month_days` [2] | refused |
| O03 | "Remind me of our anniversary on 3 June, the third reminder is the one I need" | `on_month_days` [3] | refused |
| O04 | "Remind me of Anna's birthday on 11 May and to pay rent on the first" | `on_month_days` [1] | runs |
| O05 | "On the second, pay the gym, and remind me of Tom's birthday on 2 March" | `on_month_days` [2] | runs |

O04 and O05 are the near misses: an ordinal word that is a day, at the end of the message and
before a comma, whose monthly call must keep running.

The change: an ordinal word after "the" or "every" is a day when what follows it is the end of
the message, a punctuation mark or a closed-class word (a preposition, conjunction, determiner,
pronoun, auxiliary verb, or one of a few adverbs such as "please" and "again"). Any other word is
read as the noun the ordinal describes, and the word is then no day. The closed-class list is
finite by nature, so a missed noun adds nothing to it. Its known limit is an imperative verb
right after the day with no comma ("on the second pay the gym"): that call is refused once, and a
retry on the same days runs.

The rule:

1. The change ships when the unit tests hold all five rows (O01 to O03 refused, O04 and O05 run),
   and the replay of every quoted string in `docs/readings/`, the task files and the brain tests
   through both readers lists each string whose days change, every one of them an ordinal word
   with a noun after it.
2. Each row is drawn once on the stack brain with the driver of the main record, and its stored
   shape is recorded. One draw decides nothing; a monthly rule stored on an O01 to O03 draw is
   filed.

## An ordinal word before a noun, 2026-11-06

The reader now reads an ordinal word after "the" or "every" as a day only when the end of the
message, a punctuation mark or a closed-class word follows it (`_AFTER_DAY` in
`schedule_yearly.py`). The unit tests hold all five rows. Replaying every quoted string in
`docs/readings/`, the task files and the brain tests, plus the test file before the change
(27,265 strings, 43 of which both readers read as a yearly date): no string gains a day, and 729
lose one. 722 of them are prose passages that name no yearly date ("the first two rows", "the
eleventh part"), which the reader never reads. The 7 strings that name a yearly date and change
are the O01 to O03 messages in their task and readings copies, the test row "Our anniversary is on
3 May, the second one we have had." (day 2 before, no day now) and one readings passage whose
"the first run" is prose. Item 1 of the rule passes.

## The five rows on a candidate brain, 2026-11-06

Drawn once each from 01:50 to 01:53 UTC on a brain built from the working tree beside the stack
brain (container `cortexn14-brain-o989`, port 23052, the stack's model host, redis and postgres),
the SM clock at 0.57 of its maximum on every row. Run log `rows989.jsonl`, the stored records
`records989.jsonl` and the tool calls `cand989-calls.log` in slot 1 of the run's scratch directory.
No turn failed, every record was deleted after its draw, and no `cortex:schedule*` key was left.

| Row | Calls in the brain log | Stored |
| --- | --- | --- |
| O01 | `on_month_days` [1], refused; then `on_dates` ["07-01"] | yearly on 07-01 |
| O02 | `on_dates` ["03-02"] | yearly on 03-02 |
| O03 | `on_dates` sent as a string, refused as invalid; then `on_dates` ["06-03"] | yearly on 06-03 |
| O04 | `on_month_days` [11], refused; `on_month_days` [1], ran; then `on_dates` ["05-11"] | monthly on day 1 and yearly on 05-11 |
| O05 | two `at` calls | one-time on 2026-12-02 and 2027-03-02 |

The O01 draw made the monthly call on day 1 that the change refuses, where the reader before it
read "the first one" as day 1 and ran it, and the draw then stored the yearly date. O04 ran the
rent call on day 1 beside the refused birthday call. O05 made no monthly call, so it tested
nothing of the reader. One draw each decides nothing, and no draw stored a monthly rule for a
birthday, so nothing is filed.
