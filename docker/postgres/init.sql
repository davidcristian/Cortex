-- Applied once, on first init of the Postgres data dir (docker-entrypoint-initdb.d),
-- by the postgres service in docker-compose.memory.yml. This is the durable store behind
-- cortex_memory's MemoryStore port (ADR-0008); the adapter assumes it already exists.
--
-- The embedding column is an UNBOUNDED vector (any dimension) and UNINDEXED: exact cosine
-- scan, which is fine at personal scale. An ANN index (hnsw/ivfflat) needs a fixed
-- dimension and is a later tuning step (ADR-0008 risk: index tuning deferred).
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memories (
    id         text        PRIMARY KEY,
    text       text        NOT NULL,
    embedding  vector      NOT NULL,
    created_at timestamptz NOT NULL
);
