# The session store still moves the hoisted set's first key

**Status:** open, waiting for its trigger
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Trigger:** a brain on a build with the move has listed, hoisted, lowered or deleted a chat
against the store that held hoisted chats under `cortex:sessions:pinned`, so
`redis-cli EXISTS cortex:sessions:pinned` answers 0 there, or that store no longer exists. The
development machine's store cannot answer it: on 2026-10-03 its append-only file has no `SADD`, so
it never held a hoisted chat under either key, and the store the move was written for is elsewhere.
**Verified:** 2026-10-03

`RedisSessionStore` in `brain/packages/session/src/cortex_session/store.py` runs
`_move_old_hoisted` once per store, before `delete`, `set_hoisted` or `list_sessions` first touches
the hoisted set (`store.py:145`, `:160` and `:172`): one `MULTI` holding
`SUNIONSTORE cortex:sessions:hoisted cortex:sessions:hoisted cortex:sessions:pinned` and
`DEL cortex:sessions:pinned`. It exists because a store that held hoisted chats before the rename
keeps them under the old key (decision 12 of ADR-0021). Once that store has moved, the step
changes nothing, costs one round trip per brain process, and keeps the old key in the code.

**What would close it.** Delete `_move_old_hoisted`, `_OLD_HOISTED_KEY`, the `_hoisted_moved` flag
and `tests/test_hoisted_key_move.py`, with the sentences in decision 12 of ADR-0021 and in the
[brain-session](../../modules/brain-session.md) module doc that describe the move. If a store that
never moved can still appear, such as a Redis restored from a backup taken before the rename, keep
the move and close this `declined` with that reason.

## History

- 2026-09-22: opened by the close of
  [R-701](701-keeping-a-chat-at-the-top-has-no-designed-name.md), which renamed the stored set.
- 2026-09-28: Not fired, and the trigger now names the store that answers it. The dev stack's
  `cortex_redis-data` volume on the development machine, last written 2026-09-17 and loaded from a
  copy, answers 0 to `EXISTS` on both keys, so it held no hoisted chat to move; that day's changes
  to `store.py` add two refusals to `append` and leave the move alone.
- 2026-10-03: Not fired, and the store the trigger named cannot answer it. A Redis 8 copy of
  `cortex_redis-data`, the only Redis volume `docker volume ls` lists on the development machine,
  answers 0 to `EXISTS` on both keys and holds 68 chats. Its append-only file, whose base is the
  empty one written when the volume was created on 2026-07-02, has 136 `ZADD` and no `SADD`, so no
  chat was ever hoisted there under either name, and the entry's "one machine with real hoisted
  chats" is not this one. The trigger now names the store that decides it, the command, and
  `delete`, the third caller of the move. `store.py` has not changed since 2026-09-28.
