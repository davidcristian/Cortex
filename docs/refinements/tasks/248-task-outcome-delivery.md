# Task-outcome delivery as a notification

**Status:** landed 2026-07-16
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Recorded first inside the grouped line naming the scheduling deferrals that the toast unblocked:
**task-outcome delivery** as a notification and a **push retry policy** beyond next-poll-pull
(both were blocked on the body half of this slice and are unblocked since the toast landed, since
the `Notify` port a task outcome would reuse now has a real backend).

Recorded in the [ADR-0025 task-outcome addendum](../../adr/ADR-0025-scheduling-reminders.md). The
entry above read true against the tree, and it decomposed into one thing to build and one to
sharpen. **What a finished task delivered before:** the ticker's `_fire_task` finished with
`deliverable=False`, so the outcome went only to the single `last_outcome` slot, read by nothing
but `list_scheduled` (`schedule_tools.py`), and a one-shot task was deleted at `finish` (terminal
cleanup) taking its outcome with it, the gap the declined occurrence-history entry named. Nothing
proactively told the user their scheduled task had run. **What the reminder path already
provided:** `_fire_reminder` finishes `deliverable=True` then pushes over `BodyGateway.notify`,
acking on a shown toast (so pull will not re-show) and staying deliverable on a declined/failed
push (so the pull path delivers), and the deliverable/ack machinery is **kind-agnostic** end to
end, `ScheduleStore.deliverable()` and the Redis `DELIVERABLE_KEY` index filter nothing by kind,
and `list_due_reminders`/`Reminders.tsx` render whatever `DueReminder`s the store yields. So a
task outcome could reuse the whole ladder with **no store, no proto, and no overlay change**.
**What landed:** `_fire_task` now finishes `deliverable=True` and calls the shared `_deliver`
(renamed from `_push`, generalized to a title+body) with the *outcome* under a `TASK_TITLE`
toast, never the standing instruction; `reminder_to_proto` maps a task's `last_outcome` into
`DueReminder.text` so the pull recovery shows the result, not the instruction. A one-shot task's
outcome now survives its fire (DONE-while-deliverable until acked), closing the one-shot half of
the occurrence-history gap for tasks. **Double-delivery is prevented by the same ack the reminder
path uses, not a resend timer:** a shown push acks (pull will not re-show), a failed push stays
deliverable (pull shows once, dismissal acks), so exactly one of push and pull ever clears the
slot; mutation-proven (dropping the task delivery reddens the delivery tests, dropping the ack
reddens the acked-not-deliverable tests, dropping the outcome mapping reddens the pull test).
Live against the compose Redis a one-shot task fired, pushed, acked, and left no `cortex:*` key,
while a body-down fire left the outcome on the deliverable index for pull.

## Trail

- 2026-07-16: The area held at 8 across this landing, which opened one entry behind it, a
  task/reminder distinction on the pull surface, the backlog working as intended.
