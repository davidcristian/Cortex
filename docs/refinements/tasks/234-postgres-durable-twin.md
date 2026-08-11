# The Postgres durable twin

**Status:** open, fix when it bites
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Trigger:** per-provenance queries or retention policies earn it.

Behind the unchanged port, when per-provenance queries or retention policies earn it (Redis AOF
on a named volume is the sessions-grade v1 tier).

## Trail

- 2026-07-16: Named by the occurrence-history closure as the store a real durable history wants,
  since such a history wants queries and retention rather than the Redis it would grow unbounded,
  so the two reopen together.
- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket this entry sits in ran against
  the tree and fired nothing.
