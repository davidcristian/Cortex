# Session and global union read policy

**Status:** open, dead until a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** Something writes durable global facts under scoping.
**Verified:** 2026-09-13

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
