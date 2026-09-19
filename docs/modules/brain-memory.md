# brain/packages/memory (`cortex_memory`)

**Purpose.** The pgvector adapter for the core's `MemoryStore` port, plus the logging adapter for
its `RecallAuditSink` port (ADR-0008, ADR-0038). It is a thin SQL translator over Postgres with
pgvector: one row per memory, and `search` ranks by cosine distance (`<=>`) and returns cosine
*similarity* as the score, so it behaves the same as `InMemoryMemoryStore` behind the port. No
business logic and no state beyond the injected pool (the one hard rule).

## Public contract

`__all__` is `Database`, `LoggingRecallSink` and `PgVectorMemoryStore`.

### `PgVectorMemoryStore(db: Database)`

- `add(record)` is `INSERT (id, text, embedding, scope, tainted, created_at)` with
  `embedding = $3::vector`, the vector passed as a pgvector text literal such as `[0.1,0.2]`.
  `tainted` is the untrusted-provenance marker (ADR-0019).
- `search(embedding, *, k, scopes=None)` is `ORDER BY embedding <=> $1::vector LIMIT $2`, mapping
  each row to `ScoredMemory(record, score = 1 - distance)`, most similar first, with each record
  keeping its `scope` and `tainted`. It reads the vector back through `embedding::text`, so no
  driver-side vector type has to be registered. A non-`None` `scopes` adds `WHERE scope = ANY($3)`
  to filter candidates to those namespaces before ranking (ADR-0008 decision 9); `None` ranks over
  every memory.
- `count_candidates(*, scopes=None)` is `SELECT count(*) AS total FROM memories` plus the same
  `WHERE scope = ANY($1)` a scoped `search` applies, so the two describe one candidate set. It
  reports the server's own count and never a `len` over the rows this adapter fetched, which is the
  distinction the method exists to draw (ADR-0038 decision 14). It is deliberately a second
  statement rather than a `count(*) OVER ()` on the ranked `SELECT`: the window function must buffer
  every candidate row, embeddings included, before the `LIMIT` can apply, measured at 2.85x the
  plain search over 100k rows, while this costs a small fraction of that because
  `memories_scope_idx` serves it as an index-only scan that never touches the vectors. It is exact
  rather than capped for the same reason. The two statements are not one transaction, which
  `RecallAudit.available` reports.
- `delete_scope(scope)` is `DELETE FROM memories WHERE scope = $1` (the `memories_scope_idx` btree
  serves the equality, so no schema change), returning the row count parsed from asyncpg's
  `DELETE n` command tag: 0 when the scope holds none, and a malformed tag wrapped as
  `MemoryStoreError`. It is a hard delete rather than a marker, because `search` is a stateless
  top-k scan with no in-flight read of one id to fail cleanly, so a removed row simply drops out of
  the candidate pool (ADR-0008 decision 11). It is the forget primitive that both the session-delete
  cascade and per-scope eviction call.
- `aclose()` releases the pool. `PgVectorMemoryStore.connect(dsn)` is the classmethod that builds a
  store owning a fresh asyncpg pool for `dsn`.

`Database` is the `Protocol` the store talks to (`execute`, `fetch`, `close`). An asyncpg pool
satisfies it in production and in the live test; a canned-row fake satisfies it in CI.

### `LoggingRecallSink()`

It is a `RecallAuditSink` (`audit.py`, ADR-0038). `record(audit)` writes one
`cortex.memory.recall` line per recall, its fields attached as `extra` and rendered onto the line by
the process entry's formatter (ADR-0051 decision 1): the conversation as `session_id`, the turn the
recall was made for as `turn_id` (ADR-0038 decision 16), the query's *length*, the pool size, how
many candidates were available, `k`, the rank basis, whether keys on that basis may be compared,
each kept hit's `id`, `score`, `key` and `tainted`, the candidates the rank dropped, and the time.
It holds **no text at all**, neither the query nor a recalled memory, which is the tool audit's
"size not content" stance applied to conversation content. It is attached by
`CORTEX_MEMORY_RECALL_AUDIT`.

The logger it writes through is declared in the module as `_LOGGER_NAME` rather than written inside
the `getLogger` call, because this contract and the two runbooks that turn the trail on and name it
restate that name and none of them can import it. `scripts/crosscheck.py` compares all three with
the declaration, so a rename here fails that check rather than leaving three documents telling an
operator to select a trail nothing writes (ADR-0045 decision 13).

A line with no hits is read through its basis and logs no separate flag for one (ADR-0038 decision
11): `"basis": "demur"` is the model having read a pool and declined all of it, any other basis with
empty `hits` is a pool that held nothing to rank, and a fallback after an unreachable or
unbelievable model shows the fallback's own basis with the hits it chose.

- The drops are on that line as `dropped`, one `{"id", "score"}` per candidate the store offered and
  the rank did not keep, plus `dropped_omitted`, how many more the bound left out (ADR-0038 decision
  13). `score` is the store's raw cosine and there is no rank key beside it, because the rank
  records no reason for a candidate it passed over, so the pair answers "was this memory even a
  candidate?" and never "why was it not kept?". The sink computes none of it: the core's
  `dropped_candidates` takes the difference and applies the bound, and `record` writes it out. The
  field holds one id per candidate, so its rendered width moves with whatever mints them; the id
  width at which it stops fitting `VALUE_CHARS` is written beside the factory itself, at
  `MemoryRecaller` in [brain-core.md](brain-core.md).
- `available` beside `pool` is how many candidates there were, against how many came back (ADR-0038
  decision 14). When the two are equal, the pool was the whole readable store, so an id on neither
  list was either never written or written outside the read scopes. When they differ, the pool was
  cut at its requested width, so a missing memory may simply have ranked below the cut. That reading
  needs nothing of the deployment's pool factor, which is why the requested width is not logged
  beside it: where it would matter it equals `pool`, and where it would not it explains nothing.

## Error contract

Every failure crosses the `MemoryStore` port as `MemoryStoreError` with the cause chained: asyncpg
`PostgresError` and `InterfaceError` and socket `OSError` from add, search, count and close; a
malformed result row (missing column, unparseable vector, naive timestamp) in `search`; and a reply
with no readable integer total in `count_candidates`. Those last two raise the **`MemoryDataError`**
subclass, which every existing `except MemoryStoreError` still catches and which says the store
answered and this code could not read the answer (ADR-0008 decision 13). The adapter can draw that
line where it wraps because the two arrive as disjoint exception types, asyncpg's own family against
a `KeyError` or `ValueError` out of `_to_scored`, so neither `except` has to classify anything; a bad embedding from the core is on the data side too, `_to_literal` being inside the `try`.

A count that fails fails the recall that asked for it, rather than degrading to a number the store
never returned; the trail's own sink already fails a recall the same way, because an audit line with
a figure the adapter invented would misreport the candidate set. **A failed recall does not fail the
turn**: the core catches `MemoryStoreError` where a turn is assembled and where its exchange is
recorded, and answers without its notes (ADR-0008 decision 12). A `MemoryDataError` does fail the
turn, `_recalled_context` naming it ahead of that catch and re-raising, because an outage clears on
its own while stored state that disagrees with the code reading it does not, so degrading around it
would answer without memory indefinitely. The adapter is unchanged by that and must stay so, since
the same store serves the session-delete cascade, where `SessionServicer` aborts `UNAVAILABLE` and a
swallowed failure would be a privacy defect.

## Schema

The schema belongs to the deployment, not the adapter: `CREATE EXTENSION vector;` plus
`memories(id text pk, text text, embedding vector, scope text not null default 'global', tainted boolean not null default false, created_at timestamptz)`
plus a btree `memories_scope_idx` on `scope`. The `embedding` column is unbounded (any dimension)
and unindexed, an exact cosine scan measured at 21 ms per search over a thousand memories and 1,478
ms over 220,000, so it is fine for months of use and dominant after years; an ANN index (fixed
dimension) is a later tuning, deferred on recall quality and on the dimension-agnostic column it
would end rather than on speed (ADR-0008, ADR-0004 decision 4, with the numbers in
`docs/readings/model-lineup.md`). `scope` is the memory's namespace (ADR-0008 decision 9) and
`tainted` its untrusted-provenance marker (ADR-0019); each column's `DEFAULT` makes it an additive
`ALTER TABLE … ADD COLUMN` on an existing database, back-filling every old row into the global space
and as trusted, since they were only ever written by untainted turns (the migration is in the
runbook). It is applied by `docker/postgres/init.sql` through `docker/docker-compose.memory.yml`.
pgvector stores float4, so embeddings round-trip at single precision, which does not affect
similarity ranking.

## Invariants

- Stateless per call beyond the pool; no memory or context is held here (the one hard rule). Real
  database I/O lives here and never in the core.
- Fully typed, pyright strict clean (asyncpg-stubs for the driver), 100% line and branch through a
  canned-row fake `Database`, with no Postgres and no network.
- The shared checks in `tests/memory_contract.py` drive **both** implementations:
  `tests/test_memory_store_contract.py` runs the same file over `InMemoryMemoryStore` in CI. Until
  it did, a check added to the shared file reached CI only if someone remembered to write it a
  second time by hand in `cortex_core`'s tests, which is how a count faked as a length over rows
  would have stayed invisible to everyone without a database. Each check takes a
  `MemoryStoreUnderTest`, the implementation plus an awaited `break_backend`, so the port's failure
  channel is checked where its values are: the eleventh check breaks the backend and requires `add`,
  `search`, `count_candidates` and `delete_scope` each to raise `MemoryStoreError` rather than the
  driver's own exception, and not the `MemoryDataError` subclass either, since an outage misread as
  a data defect would fail the very turn the degradation exists to save. The other direction is
  deliberately not a shared check: the in-memory twin decodes nothing, so only the implementation
  with rows can meet a row it cannot read, and `test_pgvector.py` covers that half. The fake is
  scripted with `fail_with`; the live run passes the adapter's own `aclose`, so the real pool closes
  and asyncpg's `InterfaceError` crosses this adapter's own wrapping (ADR-0008 decision 6).
- The behavioural contract against real pgvector is the `integration`-marked
  `tests/test_pgvector_live.py` (`CORTEX_MEMORY_DSN`), excluded from CI and coverage and run per
  [docs/runbooks/memory-pgvector.md](../runbooks/memory-pgvector.md). That run **owns the
  `cortex_contract` database** and empties it before the suite and after every check
  (`tests/live_postgres.py`, the Postgres twin of the session package's `live_redis.py`), so it
  starts from the same empty store the in-memory fake does and never touches the brain's memories,
  which the two checks asserting over the whole table (`check_empty_search`,
  `check_ranks_by_similarity`) used to require by luck. The database is bootstrapped from this same
  schema by `docker/postgres/live-contract-db.sql` through the compose file, and the run stops
  rather than falling back when that database is absent (ADR-0002 decision 15).

**Dependencies.** cortex-core (the `MemoryStore` port, `MemoryRecord` and `ScoredMemory`, and the
typed errors) and asyncpg with asyncpg-stubs. The composition root
(`cortex_orchestrator.wiring.build_memory`) injects the pool when `CORTEX_MEMORY_BACKEND=pgvector`.
