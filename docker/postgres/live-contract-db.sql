-- Applied once, on first init of the Postgres data dir (docker-entrypoint-initdb.d), by the
-- postgres service in docker-compose.memory.yml, alongside init.sql. It creates the database the
-- integration-marked MemoryStore contract run owns (brain/packages/memory/tests/live_postgres.py)
-- so that run never reads, writes, or empties the brain's own `memories` table.
--
-- The bootstrap this database gets is the SAME file the brain's gets, included rather than
-- restated, because pgvector is installed per DATABASE (not per schema): a second database needs
-- its own `CREATE EXTENSION vector` and its own `memories` table, and a second copy of that DDL
-- would be free to drift from the one the adapter is actually tested against.
--
-- Nothing points the brain here: docker-compose.memory.yml sets CORTEX_MEMORY_DSN to the `cortex`
-- database, and the live run refuses to start when it is pointed at this one.
--
-- An existing data dir never re-runs an initdb script, so a machine whose volume predates this
-- file bootstraps by hand (the same two statements, from docs/runbooks/memory-pgvector.md):
--   psql -U cortex -d cortex -c 'CREATE DATABASE cortex_contract;'
--   psql -U cortex -d cortex_contract -f /docker-entrypoint-initdb.d/init.sql
CREATE DATABASE cortex_contract;

\connect cortex_contract

\i /docker-entrypoint-initdb.d/init.sql
