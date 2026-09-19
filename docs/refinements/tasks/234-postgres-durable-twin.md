# The Postgres durable copy

**Status:** declined 2026-08-18
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

Proposed: a Postgres schedule store behind the unchanged port, once per-provenance queries or
retention policies justified it. What ships is Redis with append-only persistence on a named
volume.

Declined, on four findings from the code:

- Its only named consumer waits on the same missing reader. This entry said it would reopen
  together with the occurrence-history table, and nothing in the tree reads a fired occurrence,
  which is what settled that entry ([242](242-occurrence-history.md)).
- Neither trigger can occur. Nothing queries a schedule by provenance: the only listing reads are
  `list_active()`, used by the creation cap and by `list_scheduled`
  ([schedule_tools.py](../../../brain/packages/core/src/cortex_core/schedule_tools.py)), and
  `deliverable()` for the reminder pull, and neither takes a session argument. Nothing needs a
  retention policy either: a finished one-shot deletes its own record on `ack`, and the active set
  is capped at 32 by configuration. The one key that grows is the dead-letter hash, which needs a
  purge rather than a second database ([245](245-automated-dead-letter-retention.md)).
- The durability argument runs backwards. `SessionStore` has no backend switch: the composition
  root wires `RedisSessionStore` unconditionally. Conversation history, the state the one hard rule
  exists to protect, is Redis only, so a Postgres schedule store would make reminders more durable
  than the transcript they belong to. If Postgres is ever the answer here, it is the answer for
  sessions first.
- The cost is not "behind the unchanged port" any more. `snooze` and `edit` joined the port, which
  now has eleven methods over an adapter spread across four modules, plus a shared contract suite
  of 665 lines whose fencing races are its whole point. There is no fake Postgres the way
  `fakeredis` stands in for Redis, so those races could only be tested against a real server in an
  `integration`-marked suite that CI never runs.

## History

- 2026-07-16: Named by the occurrence-history closure as the store a real durable history would
  need, since such a history needs queries and retention, so the two would reopen together.
- 2026-08-09: A review of the entries deferred until they cause a problem found that none had.
- 2026-08-18: Declined, on the findings above. Recorded at the origin decision.
