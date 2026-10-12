# A reply claims a task it never tried to schedule

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-10-12

In the third turn of a chat (a question about a file holding an injection, a reminder, then "Read
meeting-notes.txt again, then schedule a background task for tomorrow at 10:00 that checks
whether the bulb order went out."), the cortex sometimes reads the file and makes no
`schedule_task` call at all, then replies "I've scheduled a background task for you". It did so
once through the overlay, in 5 of 15 third turns over `Converse` on 2026-10-10, and in 1 of 10
on 2026-10-12 ([readings](../../readings/task-claimed-without-call.md#results)). No result text
reaches this reply, since no tool ran: `TAINTED_TASK_MSG`, which every other repeat received,
makes them say the task was not scheduled.

Recall is not the source. The 2026-10-12 claim had no recalled row, and no refusal text was in
its chat; the only scheduling it saw was its own turn 2, replayed as a `schedule_task` call that
succeeded, with "I've set a reminder" as the reply. Turns that recalled five exchanges saying a
reminder was set all made their own call.

## What to do

1. Tell the chat's own reminder turn from the model alone: the chain with memory emptied before
   each chain, 20 chains with turn 2 the reminder and 20 with turn 2 a question that schedules
   nothing, counting claims. Write the rule into the readings before the run.
2. Then pick the remedy, measured on the same rows. The candidates: the brain checks a reply that
   says something was scheduled against the turn's runs and closes it with a typed note when no
   `schedule_task` call succeeded (a heuristic on reply text, so count its false matches on
   replies that only name stored items), or, if turn 2 is the source, the replayed call names
   its kind and text so an earlier reminder is not read as this turn's task.

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
