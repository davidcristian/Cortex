# Occurrence history

**Status:** declined 2026-07-16
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Proposed: a table of past fires. Deliverability uses one coalesced slot and keeps no per-fire
record, and terminal cleanup deletes a one-shot task's outcome with its record, so a history table
would also let the user recover a toast they never saw.

The problem is real and was verified live against the compose Redis. A fired reminder sets the
single `deliverable_since` slot, cleared at `ack` and overwritten if it fires again first; a task
overwrites the single `last_outcome`; a terminal one-shot is deleted at `finish` and takes its
outcome with it; and a one-shot reminder the body reports as `shown` is acked by the ticker at
once, so `RedisScheduleStore.ack` deletes its DONE record. In the live run, after a one-shot fired
and was acked there were zero `cortex:*` keys left, a recurring item survived the fire with
`deliverable_since=None` and `last_outcome=None`, and a one-shot task's `ran: 3 emails` outcome was
gone with its record.

Declined because nothing reads a fired occurrence. The gRPC boundary offers only `ListDueReminders`
(which maps the `deliverable()` awaiting-ack slot) and `AckReminder` (`proto/body.proto`);
`Reminders.tsx` renders that slot, and acking removes a row, so it cannot double as a history view.
`list_scheduled` reads `last_outcome`, but only the single last line of a still-active item, never
a series. The recovery surface this entry wants does not exist, and building it is a full stack: a
new store read the in-memory fake must also implement, a retention policy on an otherwise unbounded
write-only log, a new `BrainService` RPC, a `BrainTransport`/`BrainBridge` method with its Rust and
Tauri adapters, and a new overlay component. The origin ADR rejected per-occurrence records for
this reason, so building the record now would ship the growth policy it warned about with nothing
to shape it.

A real durable history would need queries and retention, which means the Postgres store rather than
the Redis this would grow without bound ([234](234-postgres-durable-twin.md)). It reopens the first
time a surface reads a fired occurrence, and then the record and that surface are designed
together.

## History

- 2026-07-16: Closed for want of a consumer. The store keeping no per-fire record was verified live
  against the compose Redis.
- 2026-07-16: The one-shot task half narrowed later the same day when task-outcome delivery was
  added: a fired task now finishes deliverable, so its outcome survives its fire until acked
  instead of being deleted with the record. The reminder-side missed-toast gap and the queryable
  series history stay as recorded.
