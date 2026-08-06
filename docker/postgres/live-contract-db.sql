-- Applied once beside init.sql, when the Postgres data directory is first created. It gives the
-- live MemoryStore contract tests a database of their own, set up from init.sql itself because
-- pgvector is installed per database. An older data directory: docs/runbooks/memory-pgvector.md.
CREATE DATABASE cortex_contract;

\connect cortex_contract

\i /docker-entrypoint-initdb.d/init.sql
