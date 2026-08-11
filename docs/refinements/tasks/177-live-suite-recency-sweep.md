# Recency-index sweep in the live-Redis session suite

**Status:** landed 2026-07-14
**Area:** session-read-seam
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)

Its `finally` deleted only
`cortex:session:{id}:messages` keys, leaving every run's `contract-<uuid>` ids as dangling
`cortex:sessions` members, and it recorded ids only from checks that RETURNED, so a failing
check leaked its keys too. Past 50 accumulated members,
`check_list_sessions_orders_and_summarizes` no longer found its own two sessions inside
`list_sessions(limit=50)` and failed with a bare `AssertionError`, blaming the adapter for the
test's residue (observed at 54 stale members). It now sweeps by key pattern plus the index,
scoped to the `contract-` prefix so real sessions are never touched, after each check and again
in a `finally`, matching `test_schedule_live.py`; a sweep before the first check heals a store a
killed run left dirty. The checks return `None`, since sweeping by pattern covers what a raising
check never reported. **Residual, and no sweep can reach it:** the check still asserts over a
fixed `limit=50` window with message timestamps fixed in the past, so a live Redis holding 50 or
more *real* sessions more recent than those crowds it out and fails identically. Fix when it
bites, by dating the check's messages from a clock or by reading a larger window.

**The residual closed 2026-08-03, and its own sizing was the thing that went wrong
([ADR-0002 addendum on the live-run database](../../adr/ADR-0002-toolchain-gates.md)).** Fifty was
right for the check this entry was looking at. Two days after it was written, the pinning
addendum landed `check_a_pinned_chat_escapes_the_recency_window`, which reads `limit=3` because
its three newer chats must BE the window for the pin to be the only reason the old chat lists.
That lowered the trigger from fifty real sessions to three and nobody came back to this
paragraph, so the entry kept saying fifty while the code needed three. Sixteen real sessions
later the live run failed, blaming a correct adapter exactly as described. Neither fix this
entry proposed was taken: dating the fixtures from a clock is a lie that breaks the moment real
data is future-dated, and a larger window cannot help a check whose subject is the window. The
live runs now select a Redis logical database of their own
(`brain/packages/session/tests/live_redis.py`), emptied before the suite and after every check,
so every check starts from the empty store the fakeredis fixture already gives it and the sweep
this entry landed is gone with the shared keyspace that needed it. Nothing in this seam changed:
`RedisSessionStore` keeps its key layout and `list_sessions` its union and its two round trips.

## Trail

- 2026-07-14: The suite learned to sweep by key pattern plus the index, recorded as the
  [ADR-0021 sweep addendum](../../adr/ADR-0021-session-read-seam.md), leaving the fixed-window
  residual no sweep could reach.
- 2026-08-03: The fixed-window residual closed when the live Redis runs took a Redis logical
  database of their own, which the index records against this area and against
  [repo-gates.md](../index.md#repo-gates).
