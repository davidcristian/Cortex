# A reply giving a reminder a new time with no update verb gets no note

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-11

`claims_scheduled` in `schedule_claim.py` reads a change of a reminder only through a verb of
change (`updated`, `changed`, `moved` and the like) or of setting. A reply that states the new
time with another verb reads no claim, so with no scheduling call run it gets no
`UNSCHEDULED_CLAIM_NOTE`: `Done, your 9:00 reminder now goes off at 9:30.` reads none under the
reader of 2026-11-11 ([readings](../../readings/schedule-change-request.md#the-draws-2026-11-11)).
No live draw has shown the form; 16 draws of a change or a move all ran `edit_scheduled`.

## What to do

1. Write near misses as tests first: a reply describing a reminder that exists (`Your reminder
   goes off at 9:00.`), a question, a condition, a negation, and `now` beside a fact the person
   keeps (`Your alarm code is now 5528.`).
2. Read `now` with a verb of firing (`goes off`, `fires`, `rings`) or `is now at` and a time, in a
   sentence naming a reminder or alarm, as a claim. The note's safe direction is to show.
3. Replay the readings strings and the recorded driver replies through the old and new reader.

## History

- 2026-11-11: filed from R-1134, whose fourth reply has no update verb.
