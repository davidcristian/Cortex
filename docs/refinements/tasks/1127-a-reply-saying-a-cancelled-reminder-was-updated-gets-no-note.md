# A reply saying a cancelled reminder was updated gets no note

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-10

On 2026-11-10 at 06:00 local, chat `s14-e2` on the shared stack (gemma 12B cortex) stored `Remind
me every day at 10:00 to water the plants.`, then answered `Change my plant reminder to 9:30 every
day from tomorrow on.` with `list_scheduled` and `cancel_scheduled` only. The cancel card was
approved, so the item was deleted, and the reply said `I've updated your plant reminder. It is now
set to 9:30 every day, starting from tomorrow.` No reminder was left, and no note closed the reply.
The same message in chat `s14-e1` called `edit_scheduled` with `starting` and was correct.

`unscheduled_claim` (`schedule_claim.py`) missed the claim twice. `cancel_scheduled` is not in
`SCHEDULING_TOOLS`, so the turn counts as one with no scheduling call, but `_SET` has no `updated`
or `changed`, and `is now set` stands in a sentence that names the reminder only as `It`, while
`_claim` needs a schedule noun in the same sentence.

## What to do

1. Write near misses as tests first: `I've updated your reminders: the plant one is cancelled.`,
   `I've updated your notes file.`, `It is now set to 9:30.` after a sentence naming a file, a
   question, and a negation. Replay every readings string through the old and new reader.
2. Read `updated`, `changed` or `moved` beside a schedule noun as a claim, and `It is now set`
   when the sentence before it names a reminder or task. Its safe direction is to show the note.
3. Consider a note on a turn whose cancel ran under a message asking to change an item, naming
   the item deleted; draw the message above at least eight times to count how often a change is
   answered by a cancel alone.

## History

- 2026-11-10: filed from a live store and change flow during the second audit.
