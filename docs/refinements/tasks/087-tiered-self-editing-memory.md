# Tiered and self-editing memory with summarization

**Status:** open, waiting for a consumer
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)
**Trigger:** A turn handed a superseded fact beside its correction answers with the superseded one,
once recalled memories show their dates as R-899 proposes. Read it on rows like those of the
memory over time flows: a fact changed in separate chats, then asked in a new one.
**Verified:** 2026-10-26

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
reach it, and the `MemoryRecaller` a turn is handed exposes only record and recall. Since
2026-10-14 one built-in does delete memories: `forget_untrusted_memories`, a confirmed record
card, calls the second removal, `delete_tainted`, over the scopes the chat reads. It removes by the
`tainted` flag alone and edits nothing, so it is not the self-editing this entry describes.

Still deferred, each for want of a consumer rather than a missing verb: update in place, tiered
promote, demote and expire, write salience
([R-093](093-write-salience-policy.md)), and the per-scope retention policy
([R-085](085-per-scope-retention-eviction.md)). Per-provenance eviction
([R-074](074-per-provenance-eviction.md)) needs a different filter, since a memory
record stores only the `tainted` flag and not the ADR-0027 structured provenance.

## History

- 2026-07-16: The delete verb shipped, so the index's "Memory verbs" line moved from actionable
  with a port change to waiting for a consumer. Update in place, tiered promote, demote and
  expire, write salience and the per-scope retention policy all stayed deferred, and the area's
  count did not move. The session-delete cascade that shipped the same day could finally delete
  a session's derived memories ([R-183](183-session-deletion.md)).
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
- 2026-09-30: Checked again; the trigger has not fired as far as the tree and this host show:
  no Postgres was running to join a trail against. Since 2026-09-25 the recall trail can also be
  written as JSON lines to the file `CORTEX_MEMORY_RECALL_AUDIT_FILE` names
  (`memory_builders.py:75`), each line listing the kept hits' ids (`cortex_memory/audit.py:23`),
  so the trigger names that file. `MemoryStore` still has no verb that rewrites a record,
  `MemoryRecaller.record` is still the only caller of `add`, and `SessionMemoryCascade` the only
  caller of `delete_scope`. The link to per-provenance eviction now points at its task.
- 2026-10-04: Checked again; the trigger has not fired. The host store, read this time from the
  `cortex_cortex-pgdata` volume, holds two probe rows written 2026-08-11 that state no conflicting
  facts, and no environment file in the repo sets a recall trail. `MemoryStore` is still `add`,
  `search`, `count_candidates` and `delete_scope` (`ports_stores.py:36`), with no verb that
  rewrites a record. The 2026-07-16 link to the session-delete cascade pointed at an index anchor
  that does not exist and now points at the task that shipped it.
- 2026-10-15: The trigger was not read again. The body was wrong in one claim: memory is now
  reached by one tool, `forget_untrusted_memories`, which deletes the tainted rows a chat reads
  through `delete_tainted`. It updates nothing in place, so tiering and self-editing still have no
  verb. The body now says so.
- 2026-10-25: checked again and not fired: no deployment reading exists, and `MemoryStore` and
  `MemoryRecaller` still have no update verb.
- 2026-10-26: the trigger fired on the shared test stack: in two of four memory over time flows
  on the Linux shell a recall kept a superseded value beside its correction, and both answers
  named the newest value ([readings](../../readings/overlay-memory-over-time-flows.md)). The
  flow that failed kept only the oldest value, a rank defect filed as
  [R-899](899-a-recall-of-a-changed-fact-can-keep-only-its-oldest-value.md). Since a superseded
  fact beside its correction did no harm there, the trigger now names the harm that update in
  place would remove.
