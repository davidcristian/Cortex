# A request to draft a message can schedule a reminder

**Status:** open, waiting for its trigger
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Trigger:** a reminder that no message of its chat asked for is reported from a real chat
**Verified:** 2026-10-15

Asked "Write a one-line message I can send to my team saying that I have scheduled the design
review for Friday at 10.", the cortex sometimes calls `schedule_task` and stores a reminder "Design
review" for Friday at 10:00 before writing the message. Nobody asked for a reminder, and the reply
does not mention it, so the person learns of it only when it fires.

The rate is low, and these rows cannot tell whether memory raises it
([readings](../../readings/claim-note-on-a-drafted-message.md#the-unrequested-reminder-results)).
The first turn called in 1 of 5 chains on the brain before the drafted message change, in 4 of 5
right after it, and in 4 of 105 chains drawn later on the same brain: 4 of 60 with the recorded
design review exchanges in memory (noted ones, ones with a `schedule_task` run, or both) and none
of 45 with memory emptied. A replay of the 4 of 5 run, with its three rows in turn and memory left
to grow, called in 1 of 5. The drafted message change alters only the note under a reply, which a
new chat's first turn reads only through memory, and memory held fixed at the state that change
left did not bring the 4 of 5 back.

## What to do

When the trigger fires, draw that chat's request on 40 chains with memory emptied and with the
chat's memory kept, under the rule the readings write for the rate. A tool description sentence
saying that drafting a message for the person schedules nothing is the candidate once a row
calls `schedule_task` in 4 or more of 40 chains.

## History

- 2026-10-15: filed from the drafted message rows on the `cortexn5` stack.
- 2026-10-15: corrected after 105 more chains of row D under five memory conditions: the call
  came in 4 of 105, too few to split memory from the request alone, so the task waits for a real
  report.
