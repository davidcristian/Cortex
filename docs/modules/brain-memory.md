# brain/packages/memory (`cortex_memory`)

**Purpose.** The pgvector adapter for the core's `MemoryStore` port (ADR-0008). A thin SQL
translator over Postgres + pgvector: one row per memory, `search` ranks by cosine distance
(`<=>`) and returns cosine *similarity* as the score, so it is observably interchangeable
with `InMemoryMemoryStore` behind the port. No business logic, no state beyond the injected
pool (the one hard rule).

**Public contract** (everything importable from `cortex_memory`; `__all__` is the API):

- `PgVectorMemoryStore(db: Database)` is a `MemoryStore`.
  - `add(record)` → `INSERT` with `embedding = $3::vector` (the vector passed as a pgvector
    text literal, e.g. `[0.1,0.2]`).
  - `search(embedding, *, k)` → `ORDER BY embedding <=> $1::vector LIMIT $2`, mapping each
    row to `ScoredMemory(record, score = 1 - distance)`, most-similar first. Reads the vector
    back via `embedding::text`, so no driver-side vector-type registration is needed.
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
text text, embedding vector, created_at timestamptz)`. The `embedding` column is unbounded
(any dimension) and unindexed (exact cosine scan, fine at personal scale); an ANN index
(fixed dim) is a later tuning (ADR-0008). Applied by `docker/postgres/init.sql` via
`docker/docker-compose.memory.yml`. pgvector stores float4, so embeddings roundtrip at single
precision (irrelevant to similarity ranking).

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
