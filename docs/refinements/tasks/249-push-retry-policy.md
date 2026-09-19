# Push retry policy beyond next-poll-pull

**Status:** open, fix when it bites
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Trigger:** on a live desktop, a reminder or task outcome whose push failed, which then sat
unseen after the body was reachable again until the overlay was next opened, late enough that the
user says it mattered. The brain's `push failed; pull will deliver` line marks each fire that fell
to the pull path; nothing on either side logs when the overlay pulled it, so how late it was is
the user's reading.
**Verified:** 2026-09-19

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
turned on). A genuinely-safe re-push needs a **per-fire delivery id** the body dedups on, built
when the trigger above fires.

**Corrected 2026-09-19: the per-fire id is already stored, and the dedup cannot live in the body
server.** This entry used to say the id was the per-occurrence record
[242](242-occurrence-history.md) declined, so the two would reopen together. They do not. A fire
awaiting delivery is named by its item id together with its `deliverable_since` stamp, which
`finish` sets to the fire's `fired_at` and a later fire overwrites
(`brain/packages/session/src/cortex_session/schedule_delivery.py`), and the pull wire already
carries that stamp as `DueReminder.fired_at_unix_ms`. A re-push reads `ScheduleStore.deliverable()`
and names each fire by that pair, with no history table. What the push lacks is the stamp:
`NotifyRequest` carries `reminder_id` alone. The dedup is the harder half. The body server holds no
state by design (`body/crates/rpc/src/server.rs`), and a set of shown ids kept there would be lost
on the body restart that is exactly the case a re-push serves. The record that outlives the body
process is the OS's own: a Windows toast carries a `Tag` and a `Group` (`SetTag` and `SetGroup` on
`ToastNotification` in the pinned `windows` 0.58), and `ToastNotificationManager::History` lists
the toasts the app still has in the notification centre, so the body could answer `shown` for a
fire whose tagged toast is already there instead of showing it twice. Whether that history lists
an unpackaged app's toasts, and for how long, is Win32 behaviour nobody has read on a desktop, so
the lander validates it on the host. The port's failure kind does not close the gap either:
`BodyFailure.UNREACHABLE` holds both `UNAVAILABLE` and `DEADLINE_EXCEEDED`
(`brain/packages/body_client/src/cortex_body_client/failures.py`), and an `UNAVAILABLE` can follow
a request the body received, so no kind says a toast was not shown.

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
- 2026-09-11: every claim this entry makes about the tree was read against it and holds, and
  the trigger is the one claim only a live desktop can settle. `NotifyRequest.reminder_id`
  (`proto/body.proto:382`) is still handed the item id, `reminder_id=item_id` at
  `brain/packages/orchestrator/src/cortex_orchestrator/ticker.py:210`, and a `BodyGatewayError`
  there still logs "push failed; pull will deliver" and returns (lines 212 to 217), so the next
  poll's pull is still the only retry, which the method's own docstring says in the same words
  as this entry. No `delivery_id`, `fire_id` or `occurrence_id` is spelled anywhere in the
  proto, the brain or the body, and [242](242-occurrence-history.md) is still declined, so the
  per-fire record this would be built on is still absent. The trigger is a frequency, a body
  reconnecting between a failed push and the next overlay open, that only a Win32 desktop
  running the body can show, and no file in the tree records one, so this entry carries no
  verified date.
- 2026-09-13: the reading above still holds and the entry now carries a verified date, which the
  reading above withheld. `NotifyRequest.reminder_id` is still handed `item.id` in `_deliver`, a
  `BodyGatewayError` there still logs "push failed; pull will deliver" and returns, and no
  `delivery_id`, `fire_id` or `occurrence_id` is spelled in the proto, the brain, the body crates
  or the overlay. The withheld date was a misreading of the field: it holds the day somebody last
  held the claim against the code, so an entry whose trigger only a live desktop can settle still
  carries one, and the trigger stays unfired on the trail rather than in an absent field.
- 2026-09-19: re-derived. The tree still reads as the two bullets above say: `_deliver` hands
  `reminder_id=item_id` to `notify` and logs "push failed; pull will deliver" on a
  `BodyGatewayError`, the pull runs once per overlay summon
  (`body/app/src/overlay/useReminders.ts`), and no `delivery_id`, `fire_id` or `occurrence_id` is
  spelled in the proto, the brain or the body. Two things were wrong. The per-fire id is not the declined occurrence record:
  the store already keeps it as `deliverable_since`, so this entry no longer reopens with 242, and
  the dedup it needs has to live in the OS's toast history rather than the stateless body server,
  both written above. And the trigger named no reading anyone could take, so it now names the
  brain's log line that marks a fire falling to the pull path and says that the lateness is the
  user's own report. The trigger has not fired. The same stamp also fences the ack, which is filed
  as [690](690-dismissing-one-fires-card-acks-the-fire-after-it.md).
