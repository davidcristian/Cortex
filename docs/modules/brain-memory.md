# brain/packages/memory (`cortex_memory`)

**Purpose.** The pgvector adapter for the core's `MemoryStore` port, plus the logging adapter for
its `RecallAuditSink` port (ADR-0008, ADR-0038). A thin SQL
translator over Postgres + pgvector: one row per memory, `search` ranks by cosine distance
(`<=>`) and returns cosine *similarity* as the score, so it is observably interchangeable
with `InMemoryMemoryStore` behind the port. No business logic, no state beyond the injected
pool (the one hard rule).

**Public contract** (everything importable from `cortex_memory`; `__all__` is the API):

- `LoggingRecallSink()` is a `RecallAuditSink` (`audit.py`, ADR-0038). `record(audit)` writes one
  `cortex.memory.recall` line per recall, its fields set as `extra` attributes and rendered onto
  the line by the process entry's formatter (ADR-0038 rendered-fields addendum; they used to be
  JSON-serialized into the message as well, because the shipped handler printed no `extra`): the
  conversation as `session_id`, the query's *length*, the pool size, how many candidates were
  available to it, `k`, the rank basis, whether
  keys on that basis may be compared, each kept hit's `id` / `score` / `key` / `tainted`, the
  candidates the rank dropped, and the time. It carries **no text at all**, neither the query nor a
  recalled memory, which is the tool audit's "size not content" stance applied to conversation
  content. Attached by `CORTEX_MEMORY_RECALL_AUDIT`. A line with no hits is read through its basis
  and logs no separate
  flag for one (ADR-0038 abstention addendum): `"basis": "demur"` is the model having read a pool
  and declined all of it, any other basis with empty `hits` is a pool that held nothing to rank, and
  a fallback after an unreachable or unbelievable model shows the fallback's own basis with the hits
  it chose.
  - The drops ride that line as `dropped`, one `{"id", "score"}` per candidate the store offered and
    the rank did not keep, plus `dropped_omitted`, how many more the bound left out (ADR-0038
    dropped-candidate addendum). `score` is the store's raw cosine and there is no rank key beside
    it, a rank having no opinion on record about what it passed over, so the pair answers "was this
    memory even a candidate?" and never "why did the rank decline it?". The sink decides none of
    that: the core's `dropped_candidates` takes the difference and applies the bound, and `record`
    only spells it out.
  - `available` beside `pool` is how many candidates there were, against how many came back
    (ADR-0038 candidate-count addendum). Equal, the pool was the whole readable store and an id on
    neither list was never written or was written outside the read scopes; unequal, the pool was cut
    at its requested width and an absent memory may only have ranked under the cut. That reading
    needs nothing of the deployment's pool factor, which is why the requested width is not logged
    beside it: where it would matter it equals `pool`, and where it would not it explains nothing.
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
  - `count_candidates(*, scopes=None)` → `SELECT count(*) AS total FROM memories`, plus the same
    `WHERE scope = ANY($1)` a scoped `search` applies, so the two describe one candidate set. The
    server's own count and never a `len` over rows this adapter fetched, which is the distinction
    the verb exists to draw (ADR-0038 candidate-count addendum). Deliberately a second statement
    rather than a `count(*) OVER ()` on the ranked `SELECT`: the window function must buffer every
    candidate row, embeddings included, before the `LIMIT` can apply, measured at 2.85x the plain
    search over 100k rows, while this costs a small fraction of it because `memories_scope_idx`
    serves it as an index-only scan that never touches the vectors. Exact rather than capped for
    the same reason, there being nothing left to save. The two statements are not one transaction,
    which `RecallAudit.available` documents.
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
add/search/count/close; a malformed result row (missing column, unparseable vector, naive
timestamp) in `search`, and a reply carrying no readable integer total in `count_candidates`.
Those last two raise the **`MemoryDataError`** subclass, which every existing `except
MemoryStoreError` still catches and which says the store answered and this code could not read the
answer (ADR-0008 data-defect addendum). The adapter can draw that line where it wraps because the
two arrive as disjoint exception types, asyncpg's own family against a `KeyError` or `ValueError`
out of `_to_scored`, so neither `except` classifies anything; a bad embedding from the core lands
on the data side too, `_to_literal` sitting inside the `try`, which is the same side of the line
as a bad value from the table. A
count that fails fails the recall that asked for it, rather than degrading to a number that is
not the store's: the trail's own sink already fails a recall the same way, and an audit line that
quietly invents a figure is worse than one that stops. What a failed recall no longer does is fail
the **turn**: the core catches `MemoryStoreError` where a turn is assembled and where its exchange
is recorded, and answers without its notes (ADR-0008 unavailable-memory addendum). What a
`MemoryDataError` does is fail the turn anyway, `_recalled_context` naming it ahead of that catch
and re-raising, because an outage heals on its own and stored state that disagrees with the code
reading it does not, so degrading around it would answer thinly for ever. The adapter is
unchanged by that and must stay so, since the same store serves the session-delete cascade, where
`SessionServicer` aborts `UNAVAILABLE` and a swallowed failure would be a privacy defect.

**Schema (host/infra, not the adapter).** `CREATE EXTENSION vector;` + `memories(id text pk,
text text, embedding vector, scope text not null default 'global', tainted boolean not null
default false, created_at timestamptz)` + a btree `memories_scope_idx` on `scope`. The `embedding`
column is unbounded (any dimension) and unindexed (exact cosine scan, measured at 21 ms per search
over a thousand memories and 1,478 ms over 220,000, so fine for months of use and dominant after
years); an ANN index (fixed dim) is a later tuning, deferred on recall quality and on the
dimension-agnostic column it would end rather than on speed (ADR-0008, and the ADR-0004 ANN-index
addendum for the numbers). `scope` is the memory's namespace (scoping
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
  `docs/runbooks/memory-pgvector.md`. That live run **owns the `cortex_contract` database** and
  empties it before the suite and after every check (`tests/live_postgres.py`, the Postgres twin of
  the session package's `live_redis.py`), so it starts from the same empty store the in-memory fake
  does and never touches the brain's memories, which the two checks asserting over the whole table
  (`check_empty_search`, `check_ranks_by_similarity`) used to require by luck. The database is
  bootstrapped from this same schema by `docker/postgres/live-contract-db.sql` through the compose,
  and the run refuses to start rather than falling back when it is absent (ADR-0002 addendum on the
  live pgvector database).
- The shared checks in `tests/memory_contract.py` now drive **both** implementations rather than
  only the live one: `tests/test_memory_store_contract.py` runs the same file over
  `InMemoryMemoryStore` in CI (the `test_task_store_contract.py` arrangement, minus its second
  implementation, since this adapter needs a server). Until then a check added to the shared file
  reached CI only if someone remembered to write it a second time by hand in `cortex_core`'s tests,
  which is how a count faked as a length over rows would have stayed invisible to everyone without
  a database. Each check takes a `MemoryStoreUnderTest`, the implementation plus an
  awaited `break_backend`, so the port's failure channel is checked where its values are: the
  eleventh check breaks the backend and requires `add`, `search`, `count_candidates` and
  `delete_scope` each to raise `MemoryStoreError` rather than the driver's own exception, and not
the `MemoryDataError` subclass either, an outage that read as a defect failing the turn the
degradation exists to save. The other direction is not a shared check and is not meant to be: the
in-memory twin decodes nothing, so only the arm with rows can meet a row it cannot read, and
`test_pgvector.py` holds that half. The fake
  is scripted with `fail_with`; the live arm passes the adapter's own `aclose`, so the real pool
  closes and asyncpg's `InterfaceError` crosses this adapter's own wrapping (ADR-0008 addendum on
  the port's failure channel as a shared check).

**Dependencies.** cortex-core (the `MemoryStore` port, `MemoryRecord`/`ScoredMemory`, typed
errors), asyncpg (+ asyncpg-stubs for typing). The composition root
(`cortex_orchestrator.wiring.build_memory`) injects the pool when
`CORTEX_MEMORY_BACKEND=pgvector`.
