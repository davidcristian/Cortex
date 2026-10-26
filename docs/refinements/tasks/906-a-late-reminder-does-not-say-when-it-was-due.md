# A late reminder does not say when it was due

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0066](../../adr/ADR-0066-reminder-toast-and-card.md)

A reminder that falls due while the brain cannot run, as across a sleep of the machine, fires
within one poll once the brain runs again. Its toast title names the due time when the fire is
late (decision 11 of ADR-0066, `late_phrase`), but the overlay's card shows the text and an age
counted from `fired_at_unix_ms`, the moment it fired. A reminder due at 09:00 that fires at 14:00
after a sleep reads as "just now" on the card.

Two gaps stand in the way. `DueReminder` in [proto/body.proto](../../../proto/body.proto) has no
due time. And the pull path cannot compute one for a recurring item: `reminder_to_proto` in
`cortex_orchestrator/reminders.py` reads `ScheduledItem.due_at`, which `finish` has already moved
to the next occurrence, so the fire's own due time is lost once it is stored.

Reproduction ([readings](../../readings/overlay-idle-and-expiry-flows.md#the-brain-frozen-across-a-reply-and-a-reminders-due-time)):
set "Remind me in 90 seconds to check the oven." over `Converse`, then `docker pause` the brain
for 150 s and `docker unpause` it. The item's `due_at` was 03:29:34 UTC and its
`deliverable_since` 03:30:42, the thaw. On the Linux shell a new chat showed the card "Check the
oven", "2m ago", with no due time.

## What to do

1. Store the due time of a deliverable fire beside `deliverable_since` (both stores and their
   contract test), so a recurring item keeps it after `finish` moves `due_at`.
2. Add a late fire's due time to `DueReminder` (0 when on time, by the same `late_phrase` margin)
   and show it on the card in the overlay; regenerate both stubs and the committed Rust stub, and
   run `just check-shell`. Repeat the reproduction on the shell.

## History

- 2026-10-26: filed from the idle and expiry flows on the `cortexn8` stack.
