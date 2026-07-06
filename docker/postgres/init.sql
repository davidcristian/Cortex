-- Applied once, on first init of the Postgres data dir (docker-entrypoint-initdb.d),
-- by the postgres service in docker-compose.memory.yml. This is the durable store behind
-- cortex_memory's MemoryStore port (ADR-0008); the adapter assumes it already exists.
--
-- The embedding column is an UNBOUNDED vector (any dimension) and UNINDEXED: exact cosine
-- scan, which is fine at personal scale. An ANN index (hnsw/ivfflat) needs a fixed
-- dimension and is a later tuning step (ADR-0008 risk: index tuning deferred).
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
