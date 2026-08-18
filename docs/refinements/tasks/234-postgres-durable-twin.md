# The Postgres durable twin

**Status:** declined 2026-08-18
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

A Postgres schedule store behind the unchanged port, when per-provenance queries or retention
policies earn it (Redis with append-only persistence on a named volume being the sessions-grade
tier this ships with).

**Declined, on four findings from the tree rather than from the text.**

**Its only named consumer has no consumer either.** This entry's own Trail says it reopens
together with the occurrence-history table, and nothing in the tree reads a fired occurrence, which
is the ground that settled that one ([242](242-occurrence-history.md)). Two files waiting on one
absent reader is one file too many.

**Both of its stated triggers are structurally absent, not merely unfired.** Nothing anywhere
queries a schedule by provenance: the only listing reads are `list_active()`, for the creation cap
and for `list_scheduled` ([schedule_tools.py](../../../brain/packages/core/src/cortex_core/schedule_tools.py)),
and `deliverable()` for the reminder pull, and neither takes a session argument. Nothing needs a
retention policy either, because terminal records delete themselves: a finished one-shot drops its
record on `ack`, and the active set is capped at 32 by configuration. The one key that grows
without a policy is the dead-letter hash, which wants a purge rather than a second database
([245](245-automated-dead-letter-retention.md)).

**The durability argument now runs backwards.** `SessionStore` has no backend switch at all: the
composition root wires `RedisSessionStore` unconditionally. Conversation history, which is the
state the one hard rule exists to protect, is Redis-only with no Postgres twin contemplated, so
giving reminders one would make a schedule strictly more durable than the transcript it belongs to.
If Postgres is ever the answer here, it is the answer for sessions first, and that is a different
decision with a different scope.

**And the cost is nothing like "behind the unchanged port".** That framing was true when it was
written and is not now: `snooze` and `edit` joined the port, which carries eleven methods, over an
adapter spread across four modules and a shared contract suite of 665 lines whose fencing races are
its whole point. There is no fake Postgres the way `fakeredis` twins Redis, so those races could
only be proved against a real server in an `integration`-marked suite that CI never runs. The twin
would ship with weaker evidence than the adapter it duplicates, for a reader that does not exist.

## Trail

- 2026-07-16: Named by the occurrence-history closure as the store a real durable history wants,
  since such a history wants queries and retention rather than the Redis it would grow unbounded,
  so the two reopen together.
- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket this entry sits in ran against
  the tree and fired nothing.
- 2026-08-18: Declined on a re-derivation. The entry it waits with waits on an absent reader, neither
  trigger has a mechanism in the tree that could produce it, sessions have no such twin and outrank
  schedules for durability, and the "unchanged port" cost is stale by two methods and a 665-line
  contract suite. Recorded at the origin decision.
