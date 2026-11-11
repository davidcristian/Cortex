# The schedule claim reader reads a condition with already or now as a claim

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-11

`claims_scheduled` (`schedule_claim.py`) reads `is now` or `is already` before `scheduled` as a
claim, and checks a condition word only for a reminder that now goes off at a time. Called in the
brain venv on 2026-11-11, `If it is already scheduled, I can move it.` returns true, as `If it is
now scheduled, I can move it.` did before `already` was added. On a turn with no scheduling call
the reply then ends with `UNSCHEDULED_CLAIM_NOTE`, or `LISTED_UNCHANGED_NOTE` after a list. Both
notes are true, so this is the reader's safe side: a note that was not needed.

The same night's audit built every combination of up to three successful or failed list, cancel,
snooze, schedule, edit and remember calls (84 turns, `SCRATCH/slot13/combo.py`) and found no two
notes contradicting each other, no note saying nothing changed after a call changed the schedule,
and no note shown twice.

## What to do

1. Write the condition above beside claims of the same verb (`It is already scheduled.`).
2. Decide whether `_CONDITION` before the verb keeps a sentence from being a claim, and replay the
   proxy log's replies through the old and new reader before narrowing it.

## History

- 2026-11-11: filed by the second audit of the night; reproduced with a unit call.
