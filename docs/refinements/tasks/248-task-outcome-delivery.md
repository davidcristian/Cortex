# Task-outcome delivery as a notification

**Status:** done 2026-07-16
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Decided in [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md) decision 10. It was recorded
first as one of the two scheduling deferrals the toast unblocked, since the `Notify` port a task
outcome would reuse now has a real backend; the other is the push retry policy
([249](249-push-retry-policy.md)).

Before this change, the ticker's `_fire_task` finished with `deliverable=False`, so the outcome
went only to the single `last_outcome` slot, read by nothing but `list_scheduled`
(`schedule_tools.py`), and a one-shot task was deleted at `finish`, taking its outcome with it.
Nothing told the user their scheduled task had run.

The reminder path already did all of it. `_fire_reminder` finishes `deliverable=True` and then
pushes over `BodyGateway.notify`, acking on a shown toast so the pull will not show it again, and
staying deliverable on a refused or failed push so the pull path delivers it. That machinery does
not care which kind an item is: `ScheduleStore.deliverable()` and the Redis `DELIVERABLE_KEY` index
filter nothing by kind, and `list_due_reminders` and `Reminders.tsx` render whatever `DueReminder`s
the store returns. So a task outcome reuses all of it with no store, proto or overlay change.

`_fire_task` now finishes `deliverable=True` and calls the shared `_deliver` (renamed from `_push`
and generalized to a title plus a body) with the outcome under a `TASK_TITLE` toast, never the
stored instruction, and `reminder_to_proto` maps a task's `last_outcome` into `DueReminder.text` so
the pull recovery shows the result rather than the instruction. A one-shot task's outcome now
survives its fire, staying DONE while deliverable until acked.

Double delivery is prevented by the same ack the reminder path uses, not by a resend timer: a shown
push acks, a failed push stays deliverable and the pull shows it once, with dismissal acking, so
exactly one of push and pull clears the slot. Proven by mutation: dropping the task delivery fails
the delivery tests, dropping the ack fails the acked-not-deliverable tests, and dropping the
outcome mapping fails the pull test. Live against the compose Redis, a one-shot task fired, pushed,
acked and left no `cortex:*` key, while a fire with the body down left the outcome on the
deliverable index for the pull.

## History

- 2026-07-16: Closed, and one entry opened behind it: a task versus reminder distinction on the
  pull surface.
