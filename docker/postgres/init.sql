CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memories (
    id         text        PRIMARY KEY,
    text       text        NOT NULL,
    embedding  vector      NOT NULL,
    scope      text        NOT NULL DEFAULT 'global',
    created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS memories_scope_idx ON memories (scope);
