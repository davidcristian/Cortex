# Per-session and namespaced memory scoping

**Status:** landed 2026-07-06
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

A `MemoryScope` policy seam (pure core, the `HistoryWindow` pattern) maps a turn's `session_id`
to its write-scope and read-scopes; `MemoryRecord` gained an opaque `scope` and
`MemoryStore.search` an optional `scopes` filter (`WHERE scope = ANY`, default `None` = the v1
global space). `GlobalMemoryScope` (the default, keeping recall cross-session) and
`SessionMemoryScope` (per-conversation isolation) ship, selected by `CORTEX_MEMORY_SCOPE`. CI-gated
end to end over the fakes; the pgvector SQL host-validated via Docker. Remaining behind the same
seams: a **session+global union** read policy (dead until something writes durable global facts
under scoping), **per-scope retention/eviction**, and **cross-scope recall ranking**.

## Trail

- 2026-07-06: Recorded at the [ADR-0008 scoping addendum](../../adr/ADR-0008-memory-v1.md).
