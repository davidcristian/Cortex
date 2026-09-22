# The session store still moves the hoisted set's first key

**Status:** open, waiting for its trigger
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Trigger:** the maintainer's brain has listed chats, or hoisted or lowered one, on a build that has
the move, so `EXISTS cortex:sessions:pinned` on that machine's Redis returns 0.
**Verified:** 2026-09-22

`RedisSessionStore` in `brain/packages/session/src/cortex_session/store.py` runs
`_move_old_hoisted` before its first read or write of the hoisted set in each process: one `MULTI`
holding `SUNIONSTORE cortex:sessions:hoisted cortex:sessions:hoisted cortex:sessions:pinned` and
`DEL cortex:sessions:pinned`. It exists because the one machine with real hoisted chats stored them
under the old key before the feature had its name (decision 12 of ADR-0021). Once that store has
moved, the step changes nothing, costs one round trip per brain process, and keeps the old key in
the code.

**What would close it.** Delete `_move_old_hoisted`, `_OLD_HOISTED_KEY`, the `_hoisted_moved` flag
and `tests/test_hoisted_key_move.py`, with the sentences in decision 12 of ADR-0021 and in the
[brain-session](../../modules/brain-session.md) module doc that describe the move. If a store that
never moved can still appear, such as a Redis restored from a backup taken before the rename, keep
the move and close this `declined` with that reason.

## History

- 2026-09-22: opened by the close of
  [R-701](701-keeping-a-chat-at-the-top-has-no-designed-name.md), which renamed the stored set.
