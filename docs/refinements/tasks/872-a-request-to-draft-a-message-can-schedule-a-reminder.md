# A request to draft a message can schedule a reminder

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-10-15

Asked "Write a one-line message I can send to my team saying that I have scheduled the design
review for Friday at 10.", the cortex called `schedule_task` and stored a reminder "Design review"
for Friday at 10:00 before writing the message, in 1 of 5 chains on the brain before the drafted
message change and 4 of 5 after it
([readings](../../readings/claim-note-on-a-drafted-message.md#results)). Nobody asked for a
reminder, and the reply did not mention it, so the person learns of it only when it fires.

The rows do not say why. Memory held 11 recorded exchanges of the same request whose replies end
with `UNSCHEDULED_CLAIM_NOTE`, which tells the person to ask again to schedule it, and recall may
hand those to the cortex as the reason to call.

## What to do

Draw row D of those readings with memory emptied and with the noted exchanges kept, five chains
each, and count the turns that call `schedule_task`. Write the rows and the rule into the readings
before the run. If the kept memory is the source, decide whether a recorded reply should keep the
note; otherwise measure a tool description sentence that a draft request names no reminder.

## History

- 2026-10-15: filed from the drafted message rows on the `cortexn5` stack.
