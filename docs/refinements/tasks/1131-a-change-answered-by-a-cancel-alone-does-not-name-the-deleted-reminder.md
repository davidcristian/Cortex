# A change answered by a cancel alone does not name the deleted reminder

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-11-11

On 2026-11-10 at 06:00 local, chat `s14-e2` on the shared stack (gemma 12B cortex) stored `Remind
me every day at 10:00 to water the plants.`, then answered `Change my plant reminder to 9:30 every
day from tomorrow on.` with `list_scheduled` and an approved `cancel_scheduled` only, so no
reminder was left ([readings](../../readings/schedule-full-cancel.md#a-change-answered-by-a-cancel-alone)).
The reply's claim of an update now closes with `UNSCHEDULED_CLAIM_NOTE`, which is true but does
not say that the plant reminder was deleted, and a reply that names no update gets no note.

## What to do

1. Do not draw for the form again: it came in 1 of 17 draws of a change over two nights.
2. Build a note the brain appends after a turn whose `cancel_scheduled` call succeeded, where no
   `schedule_task`, `edit_scheduled` or `snooze_scheduled` call succeeded and `unscheduled_claim`
   holds, naming the item deleted. It reads no message, so it needs no guess of the request. The
   cancel result says only `cancelled <id>`, so the item's text must be read before the cancel,
   as its card is, and kept in `TaintLedger` across the handoff record. Its safe direction is to
   show; it must not invite a second cancel. Write its pass rule about what the note does on
   replayed turns, not about how often the form comes.
3. Write near misses as tests first: a message asking to cancel, one asking to replace an item
   (a cancel then a store), and a change that ran through `edit_scheduled`.

## History

- 2026-11-10: filed when the reply claim reader learned to read an update of a reminder.
- 2026-11-11: 16 draws of a change or a move of the plant reminder all ran `edit_scheduled`, so
  no change by a cancel alone came and the build was not called for
  ([readings](../../readings/schedule-change-request.md#the-draws-2026-11-11)); the remedy now
  names a note that needs no reader of the message.
