# Occurrence history

**Status:** declined 2026-07-16
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Coalesced single-slot deliverability keeps no per-fire records,
and terminal cleanup deletes a one-shot task's outcome with its record; a history table
would also cover unseen-toast recovery.

Read against the tree and recorded in the [ADR-0025 occurrence-history
addendum](../../adr/ADR-0025-scheduling-reminders.md), no consumer reads a fired occurrence. The entry
above reads true against the tree: the store keeps no per-fire record, verified live against the
compose Redis. A fired reminder sets the single `deliverable_since` slot (cleared at `ack`,
overwritten if it re-fires before the ack, so coalesced); a task overwrites the single
`last_outcome`; a terminal one-shot is deleted at `finish` (`next_due=None`, not deliverable) and
takes its outcome with it; and a one-shot reminder the body reports `shown` is `ack`ed by the
ticker at once, so `RedisScheduleStore.ack` deletes its DONE record. The live pass showed each:
after a one-shot fired and was acked there were **zero `cortex:*` keys left**, a recurring item
survived the fire with `deliverable_since=None`/`last_outcome=None` (no trace it had fired), and a
one-shot task's `ran: 3 emails` outcome was gone with its record. So the unseen-toast gap the
entry names is real: a one-shot reminder firing to an empty room is delivered by a toast nobody
saw and then vanishes, and the next overlay open reads nothing back. **What closed it is that
nothing reads a fired occurrence.** The seam exposes only `ListDueReminders` (which maps the
`deliverable()` awaiting-ack slot) and `AckReminder` (`proto/body.proto`); `Reminders.tsx`
renders that slot and acking removes a row by contract, so it cannot double as a history view
without breaking the ack it is. `list_scheduled` reads `last_outcome`, but only the single last
line of a still-active item, never a series. A recovery surface (a "recently fired"/"you missed
these" view), the entry's own consumer, does not exist, and building it is a full stack: a new
store read the in-memory fake must also answer, a growth or retention policy on an otherwise
unbounded write-only log, a new `BrainService` RPC, a `BrainTransport`/`BrainBridge` method with
its Rust and Tauri adapters, and a new overlay component. The origin ADR rejected per-occurrence
records for exactly this ("duplicate fires nobody reads at personal scale"), so building the
record blind now would ship the growth policy it warned against with nothing to shape it. **Store
note:** a real durable history wants queries and retention, which is the deferred **Postgres
durable twin** rather than the Redis this would grow unbounded, so the two reopen together. Moves
to the backlog's dead-until-a-consumer list; it **reopens** the first time a surface reads a fired
occurrence, arriving then as the record and that surface designed as one piece, not a log built
ahead of its reader.

## Trail

- 2026-07-16: Closed for want of a consumer, the same terminal outcome the blended-relevance field
  took, and the area's count went from 9 to 8. The store keeping no per-fire record was verified
  live against the compose Redis.
- 2026-07-16: The one-shot-*task* half narrowed later the same day when task-outcome delivery
  landed: a fired task now finishes deliverable, so its outcome survives its fire until acked
  instead of being deleted with the record. The reminder-side unseen-toast gap and the queryable
  series history stay as recorded.
