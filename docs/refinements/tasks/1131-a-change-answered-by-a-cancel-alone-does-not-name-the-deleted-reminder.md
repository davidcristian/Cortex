# A change answered by a cancel alone does not name the deleted reminder

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-10

On 2026-11-10 at 06:00 local, chat `s14-e2` on the shared stack (gemma 12B cortex) stored `Remind
me every day at 10:00 to water the plants.`, then answered `Change my plant reminder to 9:30 every
day from tomorrow on.` with `list_scheduled` and an approved `cancel_scheduled` only, so no
reminder was left ([readings](../../readings/schedule-full-cancel.md#a-change-answered-by-a-cancel-alone)).
The reply's claim of an update now closes with `UNSCHEDULED_CLAIM_NOTE`, which is true but does
not say that the plant reminder was deleted, and a reply that names no update gets no note.

## What to do

1. Count first: draw the change message above at least eight times on the stack and count how
   often a change is answered by a cancel alone, and what each reply then says.
2. If the form occurs, build a note the brain appends after a turn whose `cancel_scheduled` call
   succeeded under a message asking to change an item and no store or edit followed, naming the
   item deleted. Its safe direction is to show; it must not invite a second cancel.
3. Write near misses as tests first: a message asking to cancel, one asking to replace an item
   (a cancel then a store), and a change that ran through `edit_scheduled`.

## History

- 2026-11-10: filed when the reply claim reader learned to read an update of a reminder.
