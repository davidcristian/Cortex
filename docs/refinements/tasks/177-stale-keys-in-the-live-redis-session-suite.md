# Stale keys in the live-Redis session suite

**Status:** done 2026-07-14
**Area:** session-read-rpc
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)

The live-Redis session suite's `finally` deleted only `cortex:session:{id}:messages` keys, leaving
every run's `contract-<uuid>` ids as dangling `cortex:sessions` members, and it recorded ids only
from checks that returned, so a failing check leaked its keys too. Past 50 accumulated members,
`check_list_sessions_orders_and_summarizes` no longer found its own two sessions inside
`list_sessions(limit=50)` and failed with a bare `AssertionError`, blaming the adapter for the
test's own residue (seen at 54 stale members).

The first fix deleted by key pattern plus the index, limited to the `contract-` prefix so real
sessions are never touched, after each check and again in a `finally`. That left a residue no
cleanup could reach, because the check asserts over a fixed `limit=50` window with message
timestamps fixed in the past, so a live Redis holding 50 or more more recent real sessions crowds it
out and fails identically.

The real fix is that live runs now select a Redis logical database of their own
(`brain/packages/session/tests/live_redis.py`), emptied before the suite and after every check, so
every check starts from the empty store the fakeredis fixture already gives it, and the pattern
deletion is gone with the shared keyspace that needed it. Neither fix this entry proposed was taken:
dating the fixtures from a clock makes them claim a recency they do not have, and a larger window
cannot help a check whose subject is the window. `RedisSessionStore` keeps its key layout and
`list_sessions` its union and its two round trips.

The entry's own sizing was what went wrong. Fifty was right for the check it was looking at, but two
days later `check_a_hoisted_chat_escapes_the_recency_window` arrived, reading `limit=3` because its
three newer chats must be the window. That lowered the trigger from fifty real sessions to three,
and nobody came back to this entry. Sixteen real sessions later the live run failed.

## History

- 2026-07-14: The suite learned to delete by key pattern plus the index, recorded at
  [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md), leaving the fixed-window residue.
- 2026-08-03: The fixed-window residue closed when live Redis runs took a Redis logical database of
  their own ([ADR-0002](../../adr/ADR-0002-toolchain-checks.md) decision 14).
