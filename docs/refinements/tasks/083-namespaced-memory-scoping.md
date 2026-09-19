# Per-session and namespaced memory scoping

**Status:** done 2026-07-06
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

A `MemoryScope` policy port in the pure core maps a turn's `session_id` to the scope it writes to
and the scopes it reads from. `MemoryRecord` gained an opaque `scope` field, and
`MemoryStore.search` an optional `scopes` filter (`WHERE scope = ANY`, default `None` meaning the
v1 global space). Two policies ship, chosen by `CORTEX_MEMORY_SCOPE`: `GlobalMemoryScope`, the
default, which keeps recall shared across sessions, and `SessionMemoryScope`, which isolates each
conversation. Covered end to end in CI over the fakes; the pgvector SQL was tested on the host
through Docker.

Three refinements were left behind the same port: a session-and-global union read policy
([R-084](084-session-global-union-read.md)), per-scope retention and eviction
([R-085](085-per-scope-retention-eviction.md)), and cross-scope recall ranking
([R-086](086-cross-scope-recall-ranking.md)).

## History

- 2026-07-06: Recorded at [ADR-0008 decision 9](../../adr/ADR-0008-memory-v1.md).
