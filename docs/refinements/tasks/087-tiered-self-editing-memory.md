# Tiered and self-editing memory with summarization

**Status:** open, dead until a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** A memory-compaction or self-editing feature needs tiering or update in place.

Letta's good ideas, adoptable later without
the framework, per decision 1. **Cost correction:** not behind the unchanged port. `MemoryStore`
is **`add` + `search` only**, so tiering (promote, demote, expire), self-editing (update in
place), and any retention or eviction policy all need verbs the port does not have, plus the
pgvector adapter and a fake to implement them. Per-scope retention and per-provenance eviction
are blocked on the same missing verbs.
**The delete/forget verb landed 2026-07-16 ([ADR-0008 delete-scope
addendum](../../adr/ADR-0008-memory-v1.md)); the policies stay deferred.**
`MemoryStore.delete_scope(scope) -> int` hard-deletes one namespace and returns the row count, the
one verb of the several this entry named that has recorded consumers already waiting on it: a
**session-delete cascade** (which could not honestly delete a session's derived memories,
[session-read-seam.md](../index.md#session-read-seam)) and **per-scope eviction**. It is by-scope, not
by-id, because the only link from a session to its memories is the `scope` (`SessionMemoryScope`
writes `scope == session_id`), and it takes a single required scope with no wildcard so a namespace
is dropped only when named (a caller mapping a session to `GLOBAL_SCOPE` under global scoping must
never pass it). Port + contract test + fake + pgvector adapter, CI-gated at 100%, the real DELETE
host-validated against pgvector (rows 3 to 0, count 3, other scopes spared, a no-match scope
returns 0). Data-loss-safe by construction: memory is not a tool in any registry, and the
`MemoryRecaller` a turn is handed exposes only record/recall, so no tool call, tainted or not, can
spell "forget everything" (a structural test pins that surface). **Still deferred, each for want of
a consumer and not a missing verb now:** self-editing (**update** in place), **tiered**
promote/demote/expire, **write-salience** (its own entry below), and the **per-scope retention
_policy_** (the eviction verb exists; a retention scheduler deciding what to evict when does not,
and nothing drives one). **Per-provenance eviction** ([untrusted-content.md](../index.md#untrusted-content))
wants a different filter, since a memory record stores only the `tainted` bit, not the ADR-0027
structured provenance, so `delete_scope` does not serve it and it stays fix-when-it-bites.

## Trail

- 2026-07-16: The delete/forget verb this entry was bundled with landed as
  `MemoryStore.delete_scope(scope) -> int`, the one memory verb with recorded consumers already
  waiting on it, so the index's "Memory verbs" line moved from actionable-with-a-port-change to dead
  until a consumer and the residual is policy rather than seam. Self-editing update in place, tiered
  promote/demote/expire, write-salience and the per-scope retention policy all stayed deferred for
  want of a consumer, and the area's count did not move.
- 2026-07-16: The index gave the reason the landed verb deletes hard rather than tombstoning, which
  this entry states as a property and not as an argument: search is a stateless top-k scan, so there
  is no in-flight id a tombstone would protect. The session-delete cascade that shipped the same day
  cited that reasoning for its own hard delete.
