# Dismissing one fire's card acks the fire after it

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-09-19

Opened 2026-09-19 by the re-derivation of [249](249-push-retry-policy.md), which found that the
store already names a fire by its `deliverable_since` stamp and that the ack path drops it.

An ack names an item, never a fire. `AckReminderRequest` carries `reminder_id` alone
([proto/body.proto](../../../proto/body.proto)), the overlay's dismiss sends only the `reminderId`
([useReminders.ts](../../../body/app/src/overlay/useReminders.ts)), and the Redis store's `ack`
clears the item's one deliverable slot whichever fire holds it now
([schedule_delivery.py](../../../brain/packages/session/src/cortex_session/schedule_delivery.py)).
The slot is coalesced by design: a re-fire before the ack overwrites `deliverable_since` and a
task's `last_outcome`, and that is right for the store. The card is where it goes wrong. The
overlay pulls once per summon, so a card stays on screen showing the fire it was pulled for while a
later fire replaces the slot behind it.

The sequence: a recurring task fires and its push does not show (the body is unreachable, or the
user has turned toasts off, so `shown` comes back false), and its outcome waits in the slot. The
user opens the overlay and the card shows outcome N. With the overlay still open the task fires
again, its push again does not show, and outcome N+1 replaces N in the slot. The user dismisses the
card, and the ack clears outcome N+1, which nobody has seen. A recurring reminder takes the same
path and loses nothing, because every fire carries the same text. A task's outcome differs per
fire, so for a task this is a lost delivery.

The trigger this would otherwise wait for is a user noticing an outcome that never arrived, and
nothing on either surface shows that one is missing, so it is filed actionable instead.

**The fix.** The card already holds the fire's stamp as `DueReminder.fired_at_unix_ms`. Add it to
`AckReminderRequest` (proto, regenerated into both stubs); carry it through the Rust
`BrainTransport::ack_reminder`, the shell's `ack_reminder` command and the overlay bridge's
`ackReminder`; and have `ScheduleStore.ack` take it and clear the slot only when
`deliverable_since` still equals it, inside the WATCH transaction the ack already runs in,
answering `false` otherwise. The in-memory fake and the store's contract test take the same
comparison, and the ticker's own ack after a shown push passes the `fired_at` it has just finished
with. A stale ack then leaves the newer fire deliverable, and the next summon shows it.

## Trail

- 2026-09-19: Filed by the re-derivation of [249](249-push-retry-policy.md), read from the code
  rather than observed on a desktop. The same stamp is what a safe re-push would name a fire by, so
  the two entries share their first step and neither waits on the other.
