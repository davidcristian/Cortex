-- Applied once, on first init of the Postgres data dir (docker-entrypoint-initdb.d),
-- by the postgres service in docker-compose.memory.yml. This is the durable store behind
-- cortex_memory's MemoryStore port (ADR-0008); the adapter assumes it already exists.
--
-- The embedding column is an UNBOUNDED vector (any dimension) and UNINDEXED: exact cosine
-- scan. Measured 2026-08-11 (ADR-0004 ANN-index addendum), that costs 21 ms at a thousand
-- memories and 1,478 ms at 220,000, so it is fine for the first months of daily use and is
-- the whole turn after several years. An ANN index (hnsw/ivfflat) answers 268 times faster
-- and needs a FIXED dimension, which would end the "swap the embedder, no migration"
-- property ADR-0004 decision 4 keeps; it stays deferred on recall quality rather than on
-- cost (ADR-0008 risk: index tuning deferred).
--
-- `scope` is the memory's namespace (ADR-0008 scoping addendum): `MemoryScope` chooses it
-- per turn and `search` filters on it (`WHERE scope = ANY`). DEFAULT 'global' makes the
-- column additive for an existing DB. `ALTER TABLE memories ADD COLUMN scope text NOT NULL
-- DEFAULT 'global';` back-fills every pre-existing row into the one global space, so an
-- in-place upgrade keeps recalling exactly as before. The btree indexes the equality filter
-- (not the still-deferred ANN index on `embedding`).
--
-- `tainted` is the untrusted-provenance marker (ADR-0019): true when the exchange was recorded
-- from a turn that read untrusted content, so recall fences it as data. DEFAULT false is likewise
-- additive. `ALTER TABLE memories ADD COLUMN tainted boolean NOT NULL DEFAULT false;` marks every
-- pre-existing row trusted (they were only ever written by untainted turns), so an in-place upgrade
-- keeps recalling exactly as before.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memories (
    id         text        PRIMARY KEY,
    text       text        NOT NULL,
    embedding  vector      NOT NULL,
    scope      text        NOT NULL DEFAULT 'global',
    tainted    boolean     NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS memories_scope_idx ON memories (scope);
