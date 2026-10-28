# A deleted chat stays in the Redis append-only file

**Status:** open, actionable
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Verified:** 2026-10-28

On 2026-10-28, on the `cortexn9` stack, `DeleteSession` removed every Redis key of a chat that held
a typed router password, and the password was still in `/data/appendonlydir/appendonly.aof.1.incr.aof`
on the Redis volume afterwards (`grep -c -a`: 2 lines). Redis runs with `--appendonly yes` and keeps
every write in that file until it rewrites it, which by default happens only once the file has
doubled and is over 64 MB (`auto-aof-rewrite-percentage 100`, `auto-aof-rewrite-min-size
67108864`). The file was 197,688 bytes, so a deleted chat stays readable on disk for as long as a
personal assistant takes to write 64 MB. The `memories` rows a delete does remove (a private scope)
leave dead tuples in Postgres until a vacuum, which was not measured.

Reproduction: section "Remember, forget, and delete the chat" of
[overlay-privacy-flows.md](../../readings/overlay-privacy-flows.md); after the delete,
`docker exec <redis> sh -c 'grep -c -a -F <secret> /data/appendonlydir/*'`.

## What to do

1. Measure the cost of `BGREWRITEAOF` on a store of a realistic size, then decide whether the Redis
   session adapter asks for one after a delete, or the delete is documented as leaving the text on
   disk until the next rewrite.
2. Measure the same for Postgres: whether a deleted memory's text is still readable in the table's
   files before and after `VACUUM`.

## History

- 2026-10-28: filed from the privacy flows on the `cortexn9` stack.
