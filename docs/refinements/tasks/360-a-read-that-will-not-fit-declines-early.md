# A read RPC with milliseconds left still spends the round trip

**Status:** open, waiting for its trigger
**Area:** rpc-transport
**Origin:** [ADR-0061](../../adr/ADR-0061-abandoned-call-line.md)
**Trigger:** A store read whose duration is measured rather than guessed, meaning a distribution
this repo keeps rather than one number somebody picked; or the body's own bound ceasing to be
shorter than the deadline it announces, which is what currently makes the handler's own return
worth so little. Recheck the second half with
`grep -n ANNOUNCED_DEADLINE_GRACE_MS body/crates/core/src/retry/plan.rs`: a positive constant there
means the announced deadline is still the longer of the two and this has not fired. Recheck the
first with `grep -rln 'perf_counter\|time.monotonic' brain/packages/session`: no output means the
store adapter times nothing, and the 2026-09-17 reading found no test timing a served read either.
Separately, `grep -rln time_remaining brain/packages/orchestrator/src` listing only `abandon.py`
means no handler branches on the clock yet. The read handlers live in three files
(`session_servicer.py`, `preference_servicer.py` and `server.py`), so a grep of one of them cannot
answer that.
**Verified:** 2026-09-24

`ListSessions` reads `time_remaining()` nowhere. It calls `SessionStore.list_sessions` whatever the
clock says, and a caller who has already given up gets a reply written into a stream nobody reads.
The change asked for is a handler that sees milliseconds left and answers `DEADLINE_EXCEEDED` at
once rather than spending a Redis round trip.

It was weighed and declined on 2026-08-21, for two separate reasons.

The first is what "will not fit" means. A fixed floor is a number nobody has measured, and this
repo has no distribution of how long a store read takes. The setting would ship with a guess, and a
guess here is dangerous in a way a guess elsewhere is not, because being wrong low costs nothing
visible and being wrong high refuses reads that would have succeeded, and no reading in the tree
would tell an operator which they had.

The second is heavier. The body announces a deadline strictly longer than the bound it enforces
(the grace margin), so by the time the handler could see milliseconds left the caller has usually
stopped waiting and grpc.aio has cancelled the coroutine on its own clock. The handler's early
return is therefore mostly a saving of one Redis round trip on a call that is already over, bought
with a branch that answers `DEADLINE_EXCEEDED` for a deadline that has not expired. For a store
this side of a loopback socket, that trade does not pay.

What would change it is a read that is genuinely expensive. A paging cursor
([184](184-paging-cursor.md)) or a catalog large enough that a listing is a scan rather than a
round trip would make the saving worth the invented expiry, and would also produce a measurement to
set the floor from.

## History

- 2026-08-21: Filed by the close of [341](341-nothing-declines-work-it-cannot-finish.md), which
  decided all three of its shapes and built the one that was not a per-RPC policy.
- 2026-09-08: Both halves of the trigger read again and neither has fired. Five unary handlers,
  zero mentions of `time_remaining` among them; the grace margin still 250 ms and still asserted as
  an equality; still no timing of a store read anywhere in the tree. Left open with the trigger
  rewritten to name the two commands that report it.
- 2026-09-11: Both commands were run and neither half has fired. `grep -c time_remaining` over
  `session_servicer.py` prints 0, and the file still has the same five unary handlers (lines 58,
  70, 82, 93 and 119). `ANNOUNCED_DEADLINE_GRACE_MS` is still 250 at `plan.rs:79`, and
  `retry_plan.rs:465` still asserts `announced == enforced + grace` as an equality. The only reader
  of the remaining time is still `abandon.py:74`, which prints it. No `perf_counter`,
  `time.monotonic` or `Instant::now` appears in any source file of either tree, and the paging
  cursor is still open. On the reconnect entry ([023](023-converse-reconnect-first-event.md)): both
  sit in `plan.rs`, and `Converse` is exempt from everything weighed here, since `deadline_for`
  answers `None` for it (line 252), so a clock-reading branch in a read handler would change
  nothing about a turn.
- 2026-09-17: Neither half has fired, and two statements here were narrower or wider than the tree.
  The recheck named only `session_servicer.py`, which has two of the five methods the body's plan
  treats as repeatable reads (`ListSessions` and `GetSessionMessages`); `GetPreferences` is in
  `preference_servicer.py:34`, and `ListDueReminders` and `Health` are in `server.py:193` and
  `:127`. The trigger now greps the whole package, and that grep lists only `abandon.py`. That grep
  also never answered the first half, since it reports whether this entry was built rather than
  whether a read was measured, so the first half now has its own command. The 2026-09-11 entry said
  no `perf_counter`, `time.monotonic` or `Instant::now` appears in any source file of either tree.
  That holds for production source and not for tests: 21 test files read a monotonic clock, 19
  Python and 2 Rust. Two of them touch a read and neither times a served one.
  `test_fold_under_load_live.py` opens a `RedisSessionStore` and times GPU lease waits and model
  calls, and `body/crates/rpc/tests/live.rs:304` times a `list_sessions` against a peer that serves
  nothing, to measure the retry schedule. `ANNOUNCED_DEADLINE_GRACE_MS` is still 250 at
  `plan.rs:79`, still asserted as an equality at `retry_plan.rs:465`, and no commit since
  2026-09-11 touched either file. The paging cursor ([184](184-paging-cursor.md)) is still open.
- 2026-09-24: The three commands were run and neither half has fired.
  `ANNOUNCED_DEADLINE_GRACE_MS` is still 250, now at `plan.rs:25`, and the equality it is
  asserted by is now at `retry_plan.rs:376`; `brain/packages/session` times nothing; and
  `time_remaining` still appears only in `abandon.py`. The five read handlers have moved:
  `ListSessions` and `GetSessionMessages` at `session_servicer.py:41` and `:53`, `GetPreferences`
  at `preference_servicer.py:21`, and `Health` and `ListDueReminders` at `server.py:98` and `:132`.
  `deadline_for` still answers `None` for `Converse`, now at `plan.rs:136`, and the paging cursor
  ([184](184-paging-cursor.md)) is still open.
