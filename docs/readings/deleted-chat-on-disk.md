# Readings: a deleted chat's text on disk

What stays readable in the stores' files after `DeleteSession` removes a chat and the memories it
wrote, and what a Redis rewrite costs. Taken 2026-10-28 on the `cortexn9` test stack (Redis
`redis:8-alpine` with `--appendonly yes`, Postgres with pgvector) and on side containers, never on
a real data volume. The flows that found it are in [overlay-privacy-flows.md](overlay-privacy-flows.md),
section 2; the decision is [ADR-0021](../adr/ADR-0021-session-read-rpcs.md) decision 11.

## Redis append-only file

Redis writes every command to its append-only file and rewrites the file only once it has grown by
100% and is over 64 MB (`auto-aof-rewrite-percentage`, `auto-aof-rewrite-min-size`). A router
password typed in a chat deleted about an hour earlier was still on 2 lines of
`appendonly.aof.1.incr.aof` (210,143 bytes; the store held 90 keys in 2.2 MB of memory). After one
`BGREWRITEAOF` it was on 0 lines: the new base file held 78,737 bytes and the new incremental file
was empty.

| Store | Used memory | File after the rewrite | Rewrite wall time |
| --- | --- | --- | --- |
| `cortexn9` after a night of test chats | 2.2 MB | 78,737 bytes | 1.0x (reference) |
| side store, 200,000 keys of 300 bytes | 75 MB | 7.8 MB | 1.5x |
| side store, 1,000,000 keys of 300 bytes | 368 MB | 39.8 MB | 5.3x |

The wall time runs from the `BGREWRITEAOF` call until `INFO persistence` reads
`aof_rewrite_in_progress:0`, polled through `docker exec`, so the reference row is mostly the
polling's own round trips; Redis's own `aof_last_rewrite_time_sec` read 0, 0 and 1. Each side row
is the mean of two rewrites. The rewrite runs in a forked child, so no caller waits for it. The
side-store values come from `DEBUG POPULATE`, which compress better than chat text.

Method: `redis-cli BGREWRITEAOF` and `grep -c -a -F <text> /data/appendonlydir/*` in the Redis
container; the side store is `redis:8-alpine --appendonly yes --enable-debug-command yes` filled
with `DEBUG POPULATE <n> chat 300`.

## Postgres `memories` table

On the `cortex` database, after a night of test chats: 12 live rows, 12 dead tuples and no vacuum
yet (`pg_stat_user_tables.last_autovacuum` empty). The heap file still held a deleted wifi password
6 times and a deleted router password twice. Autovacuum vacuums a table once its dead tuples pass
50 plus 20% of its live rows (`autovacuum_vacuum_threshold`, `autovacuum_vacuum_scale_factor`), so
this table keeps every deleted row in its heap until it holds 53 dead tuples.

On `cortex_contract`, one row inserted and then deleted, with a `CHECKPOINT` before each count:

| After | Text in the heap file | `n_dead_tup` | WAL segments holding it |
| --- | --- | --- | --- |
| the insert | 1 | 0 | 1 |
| the `DELETE` | 1 | 1 | 1 |
| `VACUUM memories` | 0 | 0 | 1 |
| `VACUUM FULL memories` | 0 | 0 | 1 |

`VACUUM` removed the text from the heap. No vacuum removes it from the WAL: Postgres writes over a
segment file only once later writes reach it (`max_wal_size` is 1024 MB here).

Method: `psql` `INSERT`, `DELETE`, `CHECKPOINT` and `VACUUM`, then `grep -c -a -F <text>` on the
file `pg_relation_filepath('memories')` names and `grep -l` over `pg_wal/0*`.
