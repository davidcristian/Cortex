# A late reminder does not say when it was due

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)

A reminder that falls due while the brain cannot run, as across a sleep of the machine, fires
within one poll once the brain runs again. The toast shows only "Reminder" and the text, and the
overlay's card shows the text and an age counted from `fired_at_unix_ms`, the moment it fired.
Neither says when it was due, so a reminder due at 09:00 that fires at 14:00 after a sleep reads
as "just now". `DueReminder` in [proto/body.proto](../../../proto/body.proto) has no due time to
show.

Reproduction ([readings](../../readings/overlay-idle-and-expiry-flows.md#the-brain-frozen-across-a-reply-and-a-reminders-due-time)):
set "Remind me in 90 seconds to check the oven." over `Converse`, then `docker pause` the brain
for 150 s and `docker unpause` it. The item's `due_at` was 03:29:34 UTC and its
`deliverable_since` 03:30:42, the thaw. On the Linux shell a new chat showed the card "Check the
oven", "2m ago", with no due time.

## What to do

1. Add the due time of the fire to `DueReminder` and to the toast's input, and write in ADR-0066
   when a fire counts as late (a margin over the poll, written as a setting or a constant).
2. Show a late fire's due time on the card and in the toast, in the configured zone, and test
   both sides over fakes; repeat the reproduction on the shell.

## History

- 2026-10-26: filed from the idle and expiry flows on the `cortexn8` stack.
