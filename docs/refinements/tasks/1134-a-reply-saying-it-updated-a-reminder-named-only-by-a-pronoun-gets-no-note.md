# A reply saying it updated a reminder named only by a pronoun gets no note

**Status:** done 2026-11-11
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

`claims_scheduled` in `schedule_claim.py` reads an update or a move as a schedule claim only when
its sentence names a reminder or alarm, or opens with `it`, `this` or `that` after a sentence that
does. On 2026-11-10 these replies, with no scheduling call run, all read as no claim, so
`UNSCHEDULED_CLAIM_NOTE` does not show under a false claim:

- `I've updated it to 9:30.` (the reminder is named only in the person's message)
- `Your plant reminder is ready. I've updated it to 9:30.` (the pronoun is the object)
- `I've moved your 9:00 one to 9:30.`
- `Done, your 9:00 reminder now goes off at 9:30.` (no update verb)

The check was a call of `claims_scheduled` on each string in the brain venv; no live draw has
shown the form yet.

## What to do

1. Count first: draw `Move my plant reminder to 9:30.` at least eight times on the stack, and
   in the turns where no scheduling call succeeded, count the replies of each form above.
2. Write near misses as tests first: `I've updated it.` after a sentence naming an alarm code or
   a phone number, `I've moved it to the new file.`, a question and a negation.
3. Read an object pronoun right after an update or move verb as naming the reminder a sentence
   before names, and read the person's message as the sentence before the first one. The note's
   safe direction is to show.

## History

- 2026-11-10: filed from the audit of the update reading in the schedule claim reader.
- 2026-11-11: Done. 16 draws of a change or a move ran `edit_scheduled`, so the form came in
  none. `claims_scheduled` now reads `it`, `them` or `one` right after the update or move verb as
  naming the reminder the sentence before names, and the person's last message as the sentence
  before the first; 14 near misses keep no claim, and the replay added none
  ([readings](../../readings/schedule-change-request.md#the-draws-2026-11-11)). The reply with no
  update verb is filed as
  [R-1135](1135-a-reply-giving-a-reminder-a-new-time-with-no-update-verb-gets-no-note.md).
