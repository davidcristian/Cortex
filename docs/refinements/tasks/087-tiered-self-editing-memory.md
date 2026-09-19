# Tiered and self-editing memory with summarization

**Status:** open, waiting for a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** A recall on a real deployment keeps a memory beside a later one that contradicts it,
so a turn is handed a superseded fact next to its correction. Read it by joining the kept hit ids
on the recall trail (`CORTEX_MEMORY_RECALL_AUDIT`) against the `memories` table.
**Verified:** 2026-09-19

Letta's ideas about memory tiers and a model that edits its own memories, adoptable later without
the framework (ADR-0008 decision 1). This is not behind an unchanged port: tiering (promote,
demote, expire) and self-editing (update in place) both need verbs `MemoryStore` does not have,
plus a pgvector adapter and a fake to implement them.

**The delete verb shipped 2026-07-16**
([ADR-0008 decision 11](../../adr/ADR-0008-memory-v1.md)).
`MemoryStore.delete_scope(scope) -> int` deletes one namespace outright and returns the row
count. It is by scope rather than by id because the only link from a session to its memories is
the `scope` (`SessionMemoryScope` writes `scope == session_id`), and it takes one required scope
with no wildcard so a namespace is dropped only when named. Port, contract test, fake and
pgvector adapter, covered at 100% in CI; the real DELETE was tested against pgvector on the host
(rows 3 to 0, count 3, other scopes untouched, an unmatched scope returns 0). No tool call can
reach it: memory is not a tool in any registry, and the `MemoryRecaller` a turn is handed exposes
only record and recall.

Still deferred, each for want of a consumer rather than a missing verb: update in place, tiered
promote, demote and expire, write salience
([R-093](093-write-salience-policy.md)), and the per-scope retention policy
([R-085](085-per-scope-retention-eviction.md)). Per-provenance eviction
([untrusted-content.md](../index.md#untrusted-content)) needs a different filter, since a memory
record stores only the `tainted` flag and not the ADR-0027 structured provenance.

## History

- 2026-07-16: The delete verb shipped, so the index's "Memory verbs" line moved from actionable
  with a port change to waiting for a consumer. Update in place, tiered promote, demote and
  expire, write salience and the per-scope retention policy all stayed deferred, and the area's
  count did not move. The session-delete cascade that shipped the same day could finally delete
  a session's derived memories ([session-read-rpc.md](../index.md#session-read-rpc)).
- 2026-07-16: The delete is a real delete rather than a tombstone because search is a stateless
  top-k scan, so there is no in-flight id a tombstone would protect. The session-delete cascade
  cited that reasoning for its own delete.
- 2026-09-13: Checked against the port. The inventory above was stale: `MemoryStore` is now `add`,
  `search`, `count_candidates` and `delete_scope`. Neither added verb serves this entry, because
  the port still has nothing that rewrites a stored record. The trigger has not fired. The
  summarization added since is not this entry's half either: `HistoryRecap` folds the turns that
  fall out of a session's history window and lives behind `SessionStore`, so it summarizes
  conversation rather than memories.
- 2026-09-19: Checked again. The old trigger could only have fired on this entry's own work,
  since it waited for a memory-compaction or self-editing feature and those are what this entry
  would build. It now names the condition that update in place exists for, a superseded fact
  recalled beside its correction, which the recall trail and the store can show first. The trail
  logs record ids and no text, hence the join. `MemoryRecaller.record` is still the only caller
  of `MemoryStore.add`, `SessionMemoryCascade` the only caller of `delete_scope`, and no tool in
  any registry reaches memory. No commit under `brain/` since 2026-09-13 changed any of that.
