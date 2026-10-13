# A reply claims a task it never tried to schedule

**Status:** done 2026-10-13
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

In the third turn of a chat (a question about a file holding an injection, a reminder, then "Read
meeting-notes.txt again, then schedule a background task for tomorrow at 10:00 that checks
whether the bulb order went out."), the cortex sometimes reads the file and makes no
`schedule_task` call at all, then replies "I've scheduled a background task for you". It did so
once through the overlay, in 5 of 15 third turns over `Converse` on 2026-10-10, and in 1 of 10
and then 1 of 30 on 2026-10-12 ([readings](../../readings/task-claimed-without-call.md#results)).
No result text reaches this reply, since no tool ran. A second kind ends the same way after a
call: `schedule_task` is refused with `TAINTED_TASK_MSG`, and the reply says "I have set it as a
reminder instead" with no second call, in 2 of 30 third turns on 2026-10-12.

Recall is not the source: neither 2026-10-12 claim with no call had a recalled row. Whether the
chat's own reminder turn is, is not separated: with turn 2 the reminder, 2 claims with no call
in 20 chains; with turn 2 a plain question, 0 in 15
([readings](../../readings/task-claimed-without-call.md#the-reminder-turn-against-the-model-alone)).
A claim after a refused call came in both rows, so the replayed call naming its kind and text
cannot remove the defect.

## What to do

1. Measure the reply check on rows R and Q of the readings: the brain checks a reply that says
   something was scheduled against the turn's runs, and closes it with a typed note when no
   `schedule_task` call succeeded. Count its catches on the claims of both kinds, and its false
   matches on replies that only name stored items or offer a reminder ("I can still set a
   reminder"). Write the rows and the pass rule into the readings before the baseline run.

## History

- 2026-10-10: filed from the file and memory flows on the Linux shell.
- 2026-10-10: the replay of a reply's tool runs into later turns
  ([ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md)) does not settle this. It was already in
  the brain these rows ran on, and in five more chains of the same three turns, two third turns
  read the file, made no call and claimed the task
  ([readings](../../readings/schedule-one-time-and-daily.md#results)). The replay covers the
  chat's own replies; the recall of a stored exchange does not, and a reminder exchange recalled
  into a fresh chat was claimed again with no call
  ([R-836](836-a-recalled-exchange-is-claimed-again-with-no-call.md)). Whether recall is also
  the source here is not yet measured. Left open.
- 2026-10-12: re-measured on the build that states the date in a schedule listing, ten chains,
  memory emptied or kept ([readings](../../readings/task-claimed-without-call.md)). One chain
  claimed with no call and no recalled row; recall is ruled out as the source. The prose now
  gives the rates and the remaining source, and the next row and remedy candidates are listed.
  Left open.
- 2026-10-12: step 1 run, turn 2 the reminder against a plain question, 15 chains each with
  memory emptied ([readings](../../readings/task-claimed-without-call.md#the-reminder-turn-against-the-model-alone)).
  Claims: 2 and 1; the claim with no call came only with the reminder turn, 1 against 0, and a
  claim after a refused call came in both. By the rule written first, the reply check is the
  remedy to measure; the replay naming candidate is dropped. Left open.
- 2026-10-13: done. The reply check of step 1 ships as
  [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md) decision 7, on rows and a rule written
  first ([readings](../../readings/task-claimed-without-call.md#a-reply-check-against-the-turns-runs)).
  Over 50 third turns it fired on all 8 live claims, 5 with no call and 3 that said the task was
  scheduled and then that it was not, on all 7 quoted claims, and on none of 42 other replies,
  among them 10 schedule listings and 26 offers of a reminder. The claim with no call also came in
  1 of 20 chains without the reminder turn. A task claimed beside a reminder call that succeeded
  passes the check: [R-847](847-the-reply-check-misses-a-task-claimed-beside-a-reminder.md).
