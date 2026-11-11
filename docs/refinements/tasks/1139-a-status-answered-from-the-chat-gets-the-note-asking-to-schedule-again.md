# A status answered from the chat gets the note asking to schedule again

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-11

`LISTED_UNCHANGED_NOTE` replaces `UNSCHEDULED_CLAIM_NOTE` only when a `list_scheduled` call of the
turn succeeded. A status question answered from the chat with no call still reads as a claim
(`is now set for` matches `_SET`, `now goes off at` matches `_fires_now`) and ends with "Ask again
to schedule it.", which invites a second store of a reminder already stored.

Reproduction on the stack, chat `n19s7-a` on 2026-11-11: `Remind me to water the plants every day
at 9:00.`, then `Move my plant reminder to 9:30.` (an approved `edit_scheduled`), then `So my
plant reminder now goes off at 9:30 instead of 9:00, right?` and `What time does my plant reminder
go off now that you moved it?`. Both asks called no tool, answered `Your plant reminder is now set
for 9:30 every day instead of 9:00.` and `... is now set to go off at 9:30 AM every day.`, and
ended with the note ([readings](../../readings/schedule-change-request.md#the-note-after-a-list-and-a-memory-place-2026-11-11)).

## What to do

1. Decide what the brain can read on such a turn: the person's last message is a question, and an
   earlier turn of the chat ran a scheduling call that succeeded (the session store has the runs).
2. Prefer a note change over a narrower reader, so the note still shows: when the earlier turn's
   call succeeded, word it as `LISTED_UNCHANGED_NOTE` does, saying no call in this turn changed
   the schedule and asking for nothing, in all five languages.
3. Replay the recorded replies through the old and new code, and draw the two asks above again.

## History

- 2026-11-11: filed from the smoke turns of the note built for a status read after a list.
