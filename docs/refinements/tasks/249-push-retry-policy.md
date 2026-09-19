# Push retry policy beyond the next poll

**Status:** open, waiting for its trigger
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Trigger:** on a live desktop, a reminder or task outcome whose push failed, which then sat unseen
after the body was reachable again until the overlay was next opened, late enough that the user
says it mattered. The brain's `push failed; pull will deliver` line marks each fire that fell to
the pull path; nothing on either side logs when the overlay pulled it, so how late it was is the
user's own report.
**Verified:** 2026-09-19

The only retry today is the deliverable-until-acked pull. A proactive re-push would deliver twice,
because `NotifyRequest.reminder_id` is the item id, which is stable across a recurring item's
re-fires, so the body cannot tell a retry of fire N from the legitimate fire N+1, and the
`BodyGatewayError` a down body raises looks the same as a shown toast whose reply was lost. A safe
re-push needs a per-fire delivery id that the body checks against.

Corrected 2026-09-19: the per-fire id is already stored, and the deduplication cannot live in the
body server. This entry used to say the id was the per-occurrence record that
[242](242-occurrence-history.md) declined, so the two would reopen together. They do not. A fire
awaiting delivery is named by its item id together with its `deliverable_since` stamp, which
`finish` sets to the fire's `fired_at` and a later fire overwrites
(`brain/packages/session/src/cortex_session/schedule_delivery.py`), and the pull wire already
includes that stamp as `DueReminder.fired_at_unix_ms`. A re-push reads
`ScheduleStore.deliverable()` and names each fire by that pair, with no history table. What the
push lacks is the stamp: `NotifyRequest` has `reminder_id` alone.

The deduplication is the harder half. The body server holds no state by design
(`body/crates/rpc/src/server.rs`), and a set of shown ids kept there would be lost on the body
restart that is exactly the case a re-push serves. The record that outlives the body process is the
OS's own: a Windows toast has a `Tag` and a `Group` (`SetTag` and `SetGroup` on `ToastNotification`
in the fixed `windows` 0.58), and `ToastNotificationManager::History` lists the toasts the app
still has in the notification centre, so the body could return `shown` for a fire whose tagged
toast is already there instead of showing it twice. Whether that history lists an unpackaged app's
toasts, and for how long, is Win32 behaviour nobody has tested on a desktop, so whoever builds this
validates it on the host. The port's failure kinds do not help either: `BodyFailure.UNREACHABLE`
covers both `UNAVAILABLE` and `DEADLINE_EXCEEDED`
(`brain/packages/body_client/src/cortex_body_client/failures.py`), and an `UNAVAILABLE` can follow
a request the body received, so no kind proves a toast was not shown.

## History

- 2026-07-16: Unblocked when the body-side `Notify` trait and Windows toast were added, and still
  deferred on its own merits.
- 2026-07-16: Deferred again rather than built together with task-outcome delivery, because a
  proactive re-push delivers twice on a lost reply without a per-fire delivery id.
- 2026-08-09: A review against the tree found no trigger had occurred. The scheduling entries
  behind this one need a live observation rather than a reading of the code.
- 2026-09-11: Every claim about the tree still holds. `NotifyRequest.reminder_id` is still given
  the item id in the ticker's `_deliver`, a `BodyGatewayError` there still logs "push failed; pull
  will deliver" and returns, so the next poll's pull is still the only retry. No `delivery_id`,
  `fire_id` or `occurrence_id` exists in the proto, the brain or the body.
- 2026-09-13: The same reading holds, and the entry now has a verified date. The date records when
  somebody last checked the claim against the code, so an entry whose trigger only a live desktop
  can settle still has one.
- 2026-09-19: Checked again, same reading, plus the pull runs once per overlay summon
  (`body/app/src/overlay/useReminders.ts`). Two things were wrong. The per-fire id is not the
  declined occurrence record, since the store already keeps `deliverable_since`, and the
  deduplication has to use the OS's toast history rather than the stateless body server; both are
  written above. The trigger also named no reading anyone could take, so it now names the brain's
  log line. The trigger has not occurred. The same stamp now fences the ack as well, which fixed a
  later fire's task outcome being cleared when an earlier card was dismissed
  ([ADR-0025](../../adr/ADR-0025-scheduling-reminders.md) decision 5).
