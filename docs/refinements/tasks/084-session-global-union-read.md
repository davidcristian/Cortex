# Session and global union read policy

**Status:** open, waiting for a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** Something writes durable global facts under scoping, or a deployment that recorded
under `CORTEX_MEMORY_SCOPE=global` switches to `session` and its operator asks for the memories
recorded before the switch to be recalled again.
**Verified:** 2026-09-19

A read policy that returns hits from the session scope and the global scope at once. It was one
of three refinements left behind the `MemoryScope` port when per-session scoping shipped
([R-083](083-namespaced-memory-scoping.md)).

## History

- 2026-07-06: Named as one of three refinements left behind the `MemoryScope` port. The index's
  pickup order pairs it with cross-scope recall ranking, because nothing writes durable global
  facts under scoping yet.
- 2026-09-13: Checked against `scope.py` and the recall use case; the trigger has not fired.
  Neither shipped policy writes a durable global fact while scoping is on: `GlobalMemoryScope`
  writes `GLOBAL_SCOPE` but reads with no filter at all, which is the unscoped v1 behaviour, and
  `SessionMemoryScope` writes the `session_id`. A union read would union an empty namespace. The
  session-delete cascade added since (`SessionMemoryCascade`) targets exactly
  `write_scope(session_id)` and refuses `GLOBAL_SCOPE`, so a union policy stays safe only while
  its union is on the read side. A policy that also wrote globally would put a conversation's
  memories where the cascade cannot delete them.
- 2026-09-19: Checked again; no consumer has appeared. No commit under `brain/` since 2026-09-13
  adds a memory writer, a scope policy or a memory setting, `MemoryRecaller.record` is still the
  only caller of `MemoryStore.add`, and `memory_scope_from_name` still builds only the global and
  session policies. One claim above was wrong from the day it was written: the `GLOBAL_SCOPE`
  namespace is empty only on a store that never ran under global scoping. Each row is stamped
  with its scope when written, so a deployment that recorded under the default `global` and then
  set `session` keeps every earlier memory in `global`, where `SessionMemoryScope` never reads it
  and the cascade never deletes it. Rows older than the scope column sit there too, filled in by
  the column's `DEFAULT 'global'`. On such a store a union read would return the whole
  pre-switch pool to every conversation. The trigger now names that switch as its second half,
  and the memory runbook's scoping section says what a switch in either direction does to the
  rows already stored. The host's pgvector store was not queried for the scopes it holds,
  because no Postgres was running. ADR-0008 decision 9 now states this.
