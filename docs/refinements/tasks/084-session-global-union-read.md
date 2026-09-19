# Session and global union read policy

**Status:** open, dead until a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** Something writes durable global facts under scoping, or a deployment that recorded
under `CORTEX_MEMORY_SCOPE=global` switches to `session` and its operator asks for the memories
recorded before the switch to be recalled again.
**Verified:** 2026-09-19

Recorded inside the per-session and namespaced scoping entry, which named it in the sentence listing
what stayed behind the same seams when that scoping landed:

> Remaining behind the same
> seams: a **session+global union** read policy (dead until something writes durable global facts
> under scoping), **per-scope retention/eviction**, and **cross-scope recall ranking**.

## Trail

- 2026-07-06: Named as one of three refinements left behind the `MemoryScope` seam when per-session
  and namespaced scoping landed. The index's pickup order pairs it with cross-scope recall ranking,
  on the reason that nothing writes durable global facts under scoping yet.
- 2026-09-13: Re-derived against `scope.py` and the recall use-case. The trigger has not fired.
  Two scope policies ship and neither writes a durable global fact while scoping is in force:
  `GlobalMemoryScope` writes `GLOBAL_SCOPE` but reads with no filter at all, which is the
  unscoped v1 behavior rather than scoping, and `SessionMemoryScope` writes the `session_id`.
  A union read policy would therefore still union an empty namespace. One fact this entry did
  not have: the session-delete cascade that landed since (`SessionMemoryCascade`) targets
  exactly `write_scope(session_id)` and refuses `GLOBAL_SCOPE`, so a union policy stays additive
  only while its union is on the read side. A policy that also wrote globally would put a
  conversation's memories where the cascade cannot delete them.
- 2026-09-19: Re-derived. No consumer has appeared: no commit under `brain/` since 2026-09-13 adds
  a memory writer, a scope policy or a memory setting, `MemoryRecaller.record` is still the only
  caller of `MemoryStore.add`, and `memory_scope_from_name` still builds only the global and
  session policies. One claim above was wrong from the day it was written: the `GLOBAL_SCOPE`
  namespace a union would add is empty only on a store that never ran under global scoping. A
  scope is stamped on each row when it is written, so a deployment that recorded under the default
  `global` and then set `session` keeps every earlier memory in `global`, where
  `SessionMemoryScope` never reads it and the session-delete cascade never deletes it, and every
  row older than the scope column sits there too, back-filled by the column's `DEFAULT 'global'`.
  On such a store a union read has the whole pre-switch pool to return, to every conversation. The
  trigger now names that switch as its second limb, and the memory runbook's scoping section now
  says what a switch in either direction does to the rows already stored. The host's pgvector
  store was not queried for the scopes it holds: no Postgres was running during the GPU sitting
  this sweep ran beside, and none was started. Recorded in the ADR-0008 policy-switch addendum.
