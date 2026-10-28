"""The SQL statements PgVectorMemoryStore sends, one constant per statement."""

# The share lock makes a concurrent tainted delete wait for this insert to commit, and a recalled
# row that delete already removed is not counted, so the record is not stored. Both statements lock
# in id order, so neither can hold a row the other waits on while it waits on one the other holds.
INSERT = (
    "INSERT INTO memories (id, text, embedding, scope, tainted, created_at, session_id)"
    " SELECT $1, $2, $3::vector, $4, $5, $6, $7"
    " WHERE (SELECT count(*) FROM (SELECT id FROM memories WHERE id = ANY($8::text[])"
    " ORDER BY id FOR SHARE) AS kept) = $9"
)
# $1 is the vector and $2 the limit in both search statements, so the scoped one can reuse the
# same leading arguments and append its scope list as $3.
SELECT = (
    "SELECT id, text, embedding::text AS embedding, scope, tainted, created_at, session_id,"
    " 1 - (embedding <=> $1::vector) AS score FROM memories"
)
SEARCH_ALL = f"{SELECT} ORDER BY embedding <=> $1::vector LIMIT $2"
SEARCH_SCOPED = f"{SELECT} WHERE scope = ANY($3) ORDER BY embedding <=> $1::vector LIMIT $2"
FIND = (
    "SELECT id, text, embedding::text AS embedding, scope, tainted, created_at, session_id"
    " FROM memories WHERE strpos(lower(text), lower($1)) > 0"
)
FIND_ALL = f"{FIND} ORDER BY created_at, id LIMIT $2"
FIND_SCOPED = f"{FIND} AND scope = ANY($3) ORDER BY created_at, id LIMIT $2"
COUNT_ALL = "SELECT count(*) AS total FROM memories"
COUNT_SCOPED = f"{COUNT_ALL} WHERE scope = ANY($1)"
COUNT_TAINTED = f"{COUNT_ALL} WHERE tainted"
COUNT_TAINTED_SCOPED = f"{COUNT_TAINTED} AND scope = ANY($1)"
DELETE_SCOPE = "DELETE FROM memories WHERE scope = $1"
DELETE_TAINTED = (
    "DELETE FROM memories WHERE id IN"
    " (SELECT id FROM memories WHERE tainted ORDER BY id FOR UPDATE)"
)
DELETE_TAINTED_SCOPED = (
    "DELETE FROM memories WHERE id IN"
    " (SELECT id FROM memories WHERE tainted AND scope = ANY($1) ORDER BY id FOR UPDATE)"
)
DELETE_IDS = (
    "DELETE FROM memories WHERE id IN"
    " (SELECT id FROM memories WHERE id = ANY($1::text[]) ORDER BY id FOR UPDATE)"
)
DELETE_WRITTEN_BY = (
    "DELETE FROM memories WHERE id IN"
    " (SELECT id FROM memories WHERE session_id = $1 ORDER BY id FOR UPDATE)"
)
