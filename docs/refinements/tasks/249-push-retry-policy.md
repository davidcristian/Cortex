# Push retry policy beyond next-poll-pull

**Status:** open, fix when it bites
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Trigger:** a stuck-until-open outcome becoming a real gap, a body reconnecting that often.

Recorded first inside the grouped line naming the scheduling deferrals that were unblocked when
the toast landed, then inside the task-outcome delivery entry that sharpened it ([ADR-0025
task-outcome addendum](../../adr/ADR-0025-scheduling-reminders.md)).

The remaining scheduling deferrals stay: **task-outcome delivery** as a notification and a
**push retry policy** beyond next-poll-pull (both were blocked on the body half of this slice
and are unblocked since the toast landed, since the `Notify` port a task outcome would reuse
now has a real backend).

The safe retry today *is* the deliverable-until-acked pull, and a proactive re-push beyond it
double-delivers, because `NotifyRequest.reminder_id` is the item id, stable across a recurring
item's re-fires, so the body cannot tell a retry of fire N from the legitimate fire N+1, and the
`BodyGatewayError` a down body raises is indistinguishable from a shown-toast-with-a-lost-reply
(the same lost-reply idempotency hole the ack-retry split and the `converse` reconnect sharpen
turned on). A genuinely-safe re-push needs a **per-fire delivery id** the body dedups on, which is
exactly the per-occurrence record the occurrence-history entry declined for want of a consumer, so
the two reopen together. Its trigger: a body that reconnects between a failed push and the next
overlay open often enough that an outcome stuck-until-open is a real gap, built then with the
per-fire id.

## Trail

- 2026-07-16: Unblocked when the body-side `Notify` trait and Tauri toast landed, the port a
  retry would reuse now having a real backend, and still deferred on its own merits.
- 2026-07-16: Sharpened to fix-when-it-bites when task-outcome delivery landed rather than
  landing with it, because a proactive re-push double-delivers on a lost reply without the
  per-fire delivery id the declined occurrence-history record would have carried.
- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing. The index records the scheduling entries behind this one as live-observation shaped,
  their trigger being a deployment doing something rather than a file saying something, so no
  reading of the code settles them.
