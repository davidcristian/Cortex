# The deleted chat set is never trimmed

**Status:** open, actionable
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Verified:** 2026-10-29

`RedisSessionStore.delete` adds the chat's id to the Redis set `cortex:sessions:deleted`, and no
code removes one: `store.py` only writes it with `SADD` and reads it with `SISMEMBER`. Every
`DeleteSession` call adds a member, including one for an id that never held a chat. On the
`cortexn10` stack's Redis 8.10.1, `MEMORY USAGE` of a set of chat ids measured 64,278 bytes at
1,000 members, 756,694 at 10,000 and 7,172,950 at 100,000, about 72 bytes a deleted chat, growing
for as long as the store lives.

The id is needed only while a turn could still write to the chat, and while a client might still
send a turn to it (`session_deleted`). A trimmed id makes a later turn to it start a new chat
holding only that turn, which stores nothing of the deleted one.

## What to do

1. Decide the bound in ADR-0021 decision 11: a sorted set scored by the delete time and trimmed in
   the delete's pipeline past a horizon longer than any turn (a confirmation waits 120 s, a
   handoff swaps models), or a count of the newest ids kept. Name the longest turn the horizon
   covers.
2. Build it in `RedisSessionStore` and `InMemorySessionStore`, with a contract test that an id
   past the bound is no longer marked and one inside it still is, and give the stack's Redis a
   manual step if the key changes type.

## History

- 2026-10-29: filed from the refusal of a turn sent to a deleted chat, which reads the same set.
