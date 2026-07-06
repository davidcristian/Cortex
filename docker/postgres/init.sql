-- Applied once, when the Postgres data directory is first created, by the postgres service in
-- docker-compose.memory.yml. The embedding column has no fixed dimension and no index, so a search
-- is an exact cosine scan. Upgrading an older database: docs/runbooks/memory-pgvector.md.
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
