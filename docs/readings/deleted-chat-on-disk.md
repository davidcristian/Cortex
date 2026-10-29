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

## A delete while the chat's turn runs

On 2026-10-28 on the stack, a turn in chat `s12-c` was sent and the chat was deleted 3 s later,
while the cortex was still writing (run log `slot12/delrow.log` in the night's scratch directory,
the SM clock at 0.59 of its maximum). The delete returned at once. The turn ended 10 s later and
appended its reply, which put the chat back in the chat list holding only that reply, and its
exchange was stored as a `memories` row with `session_id = 's12-c'` after the cascade had run.

The same window on the store alone, two `psql` sessions on `cortex_contract` with the shipped
`INSERT` and `delete_written_by` statements (run log `slot12/race.log`):

| Row | First, held open 3 s | Then | Row the turn wrote |
| --- | --- | --- | --- |
| R1 | the insert, recalling nothing | the delete returns in 72 ms, removing the older row | kept |
| R2 | the insert, recalling the chat's older row | the delete waits 2.1 s for the insert to commit | kept |
| R3 | the delete | the insert, recalling the older row, waits and stores nothing | none |
| R4 | the delete | the insert, recalling nothing, runs at once | kept |

The delete holds only against a turn that recalled one of the rows it removes (R3). A row the turn
commits after the delete read its rows is kept, and so is any row written after the delete ended.

### The deleted set, 2026-10-29

On the `cortexn10` stack, `DeleteSession` was called over gRPC while a `Converse` turn ran in the
chat, its stream left open, with the prompt "My locker code is 5813. Write a story of about 250
words about a lighthouse keeper." Each draw read the chat list, the chat's Redis list and index
score, and its `memories` rows 2 s after the turn ended (driver `slot5/delrow.py`, logs
`slot5/before.jsonl` and `slot5/after.jsonl` in the night's scratch directory). The rule, written
before the second run: the build passes when no draw lists the chat, holds a message, scores it in
the index or keeps a memory row.

| Brain | Delete sent after | Draws | Reply shown when the delete ran | Chat listed | Messages | Memory rows |
| --- | --- | --- | --- | --- | --- | --- |
| before the deleted set | 3 s | 2 | none | 2 of 2 | 1 each | 1 each |
| with the deleted set | 3 s | 2 | none | 0 of 2 | 0 | 0 |
| with the deleted set | 12 s | 2 | 0.53 and 0.96 of the reply | 0 of 2 | 0 | 0 |

Every delete returned in under 0.1% of its turn's length, and the slowest turn took about twice as
long as the fastest, the SM clock at 0.42 to 0.59 of its maximum when the delete returned.

The `psql` rows R1 and R4 above were drawn again on the stack's `cortex` database (`slot5/race.sh`)
and kept the turn's row both times. One more row runs the order `record_exchange` now follows
(`slot5/race5.sh`):

| Row | Session A | Session B | Rows left |
| --- | --- | --- | --- |
| R5 | the insert, held open 3 s, then committed | `SADD cortex:sessions:deleted`, then the delete, returning at once | 1 after the commit |
| R5, then | `SISMEMBER` reads 1, then the shipped delete by id | | 0 |
