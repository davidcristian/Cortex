# brain/packages/memory (`cortex_memory`)

**Purpose.** The pgvector adapter for the core's `MemoryStore` port (ADR-0008). A thin SQL
translator over Postgres + pgvector: one row per memory, `search` ranks by cosine distance
(`<=>`) and returns cosine *similarity* as the score, so it is observably interchangeable
with `InMemoryMemoryStore` behind the port. No business logic, no state beyond the injected
pool (the one hard rule).

**Public contract** (everything importable from `cortex_memory`; `__all__` is the API):

- `PgVectorMemoryStore(db: Database)` is a `MemoryStore`.
  - `add(record)` → `INSERT (id, text, embedding, scope, tainted, created_at)` with `embedding =
    $3::vector` (the vector passed as a pgvector text literal, e.g. `[0.1,0.2]`). `tainted` is the
    untrusted-provenance marker (ADR-0019).
  - `search(embedding, *, k, scopes=None)` → `ORDER BY embedding <=> $1::vector LIMIT $2`,
    mapping each row to `ScoredMemory(record, score = 1 - distance)`, most-similar first (each
    record carrying its `scope` and `tainted` back out). Reads the vector back via
    `embedding::text`, so no driver-side vector-type registration is needed. A non-`None` `scopes`
    adds `WHERE scope = ANY($3)` to filter candidates to those namespaces before ranking (ADR-0008
    scoping addendum); `None` ranks over every memory.
  - `delete_scope(scope)` → `DELETE FROM memories WHERE scope = $1` (the `memories_scope_idx` btree
    serves the equality, so no schema change), returning the row count parsed from asyncpg's `DELETE
    n` command tag (0 when the scope holds none, a malformed tag wrapped as `MemoryStoreError`). A
    hard delete, not a tombstone: `search` is a stateless top-k scan with no in-flight read of one id
    to fail cleanly, so a removed row simply drops from the candidate pool (ADR-0008 delete-scope
    addendum). The forget primitive a session-delete cascade and per-scope eviction each named.
  - `aclose()` → releases the pool.
  - `PgVectorMemoryStore.connect(dsn)` (classmethod) → builds a store owning a fresh asyncpg
    pool for `dsn`.
- `Database` is the `Protocol` (`execute` / `fetch` / `close`) the store talks to. An asyncpg
  pool satisfies it in production and the live test; a canned-row fake satisfies it in CI.

**Error contract.** Every failure crosses the `MemoryStore` port as `MemoryStoreError` with
the cause chained: asyncpg `PostgresError` / `InterfaceError` and socket `OSError` from
add/search/close; a malformed result row (missing column, unparseable vector, naive
timestamp) in `search`.

**Schema (host/infra, not the adapter).** `CREATE EXTENSION vector;` + `memories(id text pk,
text text, embedding vector, scope text not null default 'global', tainted boolean not null
default false, created_at timestamptz)` + a btree `memories_scope_idx` on `scope`. The `embedding`
column is unbounded (any dimension) and unindexed (exact cosine scan, fine at personal scale); an
ANN index (fixed dim) is a later tuning (ADR-0008). `scope` is the memory's namespace (scoping
addendum) and `tainted` its untrusted-provenance marker (ADR-0019); each column's `DEFAULT` makes
it an additive `ALTER TABLE … ADD COLUMN` on an existing DB, back-filling every old row (into the
global space / as trusted, since they were only ever written by untainted turns; migration in the
runbook). Applied by `docker/postgres/init.sql` via `docker/docker-compose.memory.yml`. pgvector
stores float4, so embeddings roundtrip at single precision (irrelevant to similarity ranking).

**Invariants.**
- Stateless per call beyond the pool; no memory or context held here (the one hard rule).
- Adapter-only: real DB I/O lives here, never in the core (AGENTS.md gate 3).
- Fully typed, pyright strict clean (asyncpg-stubs for the driver); 100% line+branch via a
  canned-row fake `Database` (the asyncpg analog of `httpx.MockTransport`), with no Postgres, no
  network. The behavioral contract against real pgvector is the `integration`-marked
  `tests/test_pgvector_live.py` (`CORTEX_MEMORY_DSN`), excluded from CI + coverage; run per
  `docs/runbooks/memory-pgvector.md`.

**Dependencies.** cortex-core (the `MemoryStore` port, `MemoryRecord`/`ScoredMemory`, typed
errors), asyncpg (+ asyncpg-stubs for typing). The composition root
(`cortex_orchestrator.wiring.build_memory`) injects the pool when
`CORTEX_MEMORY_BACKEND=pgvector`.
