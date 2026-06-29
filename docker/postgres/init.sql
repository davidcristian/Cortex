CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memories (
    id         text        PRIMARY KEY,
    text       text        NOT NULL,
    embedding  vector      NOT NULL,
    created_at timestamptz NOT NULL
);
