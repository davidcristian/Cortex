# A drafted message that says it was scheduled gets the claim note

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-10-15

On the Linux shell on 2026-10-15 a person asked "Write a one-line message I can send to my team
saying that I have scheduled the design review for Friday at 10."
([readings](../../readings/overlay-long-and-unusual-input.md#text-shaped-like-the-brains-notes)).
The cortex wrote "Hi team, I've scheduled the design review for Friday at 10:00 AM.", and the brain
appended `UNSCHEDULED_CLAIM_NOTE`: "Nothing was scheduled in this turn: no scheduling call in it
succeeded. Ask again to schedule it." The next turn, "Thanks. Make it a little more formal.", got
the note again. Nobody asked for anything to be scheduled, and the note invites the person to
schedule something they did themselves.

`unscheduled_claim` in `schedule_claim.py` matches any first person "I've scheduled" sentence in a
reply. A reply drafting text in the person's voice has the same form as a false claim.

## What to do

Find a discriminator that keeps every catch counted in
[the claim readings](../../readings/task-claimed-without-call.md) and drops this case: for example,
no note when the person's own message makes the same kind of claim (`claims_scheduled(query)`), or
when it asks for text to send or write. Check the first against a message such as "I have
scheduled a call with Ana on Friday; set a reminder an hour before", where a reply saying the
reminder is set with no call is still a false claim. Write the rows and the pass rule into those
readings before the baseline, as the brief for a model-facing change requires.

## History

- 2026-10-15: filed from the long-input flows on the Linux shell.
