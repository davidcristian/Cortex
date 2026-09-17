# A read RPC with milliseconds left still spends the round trip

**Status:** open, fix when it bites
**Area:** seam-transport
**Origin:** [ADR-0024](../../adr/ADR-0024-transport-retry.md)
**Trigger:** A store read whose duration is measured rather than guessed, meaning a distribution
this repo keeps rather than one number somebody picked; or the body's own bound ceasing to be
shorter than the deadline it announces, which is what currently makes the handler's own return
worth so little. Recheck the second half with
`grep -n ANNOUNCED_DEADLINE_GRACE_MS body/crates/core/src/retry/plan.rs`: a positive constant there
means the announced deadline is still the longer of the two and this has not fired. Recheck the
first with `grep -rln 'perf_counter\|time.monotonic' brain/packages/session`: no output means the
store adapter times nothing, and the 2026-09-17 trail line found no harness timing a served read
either. Separately, `grep -rln time_remaining brain/packages/orchestrator/src` listing only
`abandon.py` means no handler branches on the clock yet, so nothing has built this entry by
another route. The read handlers live in three files (`session_servicer.py`,
`preference_servicer.py` and `server.py`), so a grep of one of them cannot answer that.
**Verified:** 2026-09-17

`ListSessions` reads `time_remaining()` nowhere. It calls `SessionStore.list_sessions` whatever the
clock says, and a caller who has already given up gets a reply written into a stream nobody reads,
which the abandonment interceptor logs and nothing else records. The shape asked for is a handler
that sees milliseconds left and answers `DEADLINE_EXCEEDED` at once rather than spending a Redis
round trip on it.

It was weighed and declined on 2026-08-21, for two reasons that are worth keeping separate.

The first is the one the shape has carried since it was written: what "will not fit" means. A fixed
floor is a number nobody has measured, and this repo has no histogram of how long a store read
takes. The knob would ship with a guess, and a guess on this particular branch is dangerous in a
way a guess elsewhere is not, because being wrong low costs nothing visible and being wrong high
refuses reads that would have succeeded. There is no reading anywhere in the tree that would tell
an operator which of the two they had.

The second is the one that only became clear on re-derivation, and it is the heavier. The body
announces a deadline strictly longer than the bound it enforces (the grace margin), so by the time
the handler could see "milliseconds left" the caller has usually stopped waiting already, and
grpc.aio has cancelled the coroutine on its own clock. The handler's early return is therefore
mostly a saving of one Redis round trip on a call that is already over. That is real but small, and
it is bought with a branch that answers `DEADLINE_EXCEEDED` for a deadline that has **not** expired:
the brain would be inventing an expiry, on its own reading, some milliseconds before the real one.
For a store this side of a loopback socket, that trade does not pay.

What would change it is a read that is genuinely expensive, which is what the trigger names. A
paging cursor ([184](184-paging-cursor.md)) or a catalog large enough that a listing is not a
round trip but a scan would make the saving worth the invented expiry, and would also be the thing
that finally produces a measurement to set the floor from.

Both halves were reread on 2026-09-08 and both still hold. `session_servicer.py` spells
`time_remaining` zero times across all five of its unary handlers (`ListSessions`,
`GetSessionMessages`, `RenameSession`, `DeleteSession`, `SetSessionPinned`), so no read consults
the clock before spending its round trip. The only reader in the brain is the abandonment
interceptor, which prints the value and branches on nothing
(`brain/packages/orchestrator/src/cortex_orchestrator/abandon.py:74`, and the module doc above it
says so). The grace margin is still `ANNOUNCED_DEADLINE_GRACE_MS = 250`
(`body/crates/core/src/retry/plan.rs:79`), asserted as an equality rather than an inequality by
`body/crates/core/tests/retry_plan.rs:465`, so the announced deadline remains exactly 250 ms longer
than the bound the body enforces and the handler's early return would still be inventing an expiry.
The measurement that would set a floor is still absent: no histogram or timing of a store read
exists anywhere in the tree, and the paging cursor that would make one worth taking
([184](184-paging-cursor.md)) is itself still open, fix when it bites.

## Trail

- 2026-08-21: Filed by the close of
  [341](341-nothing-declines-work-it-cannot-finish.md), which decided all three of its shapes and
  built the one that was not a per-RPC policy. Recorded in the ADR-0024 addendum on what the
  announced deadline is worth downstream.
- 2026-09-08: both halves of the trigger reread and neither has fired. Five unary handlers,
  zero mentions of `time_remaining` among them; the grace margin still 250 ms and still asserted
  as an equality; still no timing of a store read anywhere in the tree. Left open with the trigger
  rewritten to name the two commands that report it, recorded in the ADR-0024 addendum on what the
  two seam-transport triggers read on this date.
- 2026-09-11: both prescribed commands were run and neither half has fired. `grep -c
  time_remaining` over `session_servicer.py` prints 0, and the file still holds the same five
  unary handlers (lines 58, 70, 82, 93 and 119). `ANNOUNCED_DEADLINE_GRACE_MS` is still 250 at
  `plan.rs:79`, and `retry_plan.rs:465` still asserts `announced == enforced + grace` as an
  equality. The only reader of the remaining time is still `abandon.py:74`, which prints it. No
  `perf_counter`, `time.monotonic` or `Instant::now` appears in any source file of either tree,
  so no store read is timed anywhere, and the paging cursor is still open. Where this touches
  the reconnect entry ([023](023-converse-reconnect-first-event.md)): both sit in `plan.rs`, and
  `Converse` is exempt from everything this entry weighs, since `deadline_for` answers `None`
  for it (line 252) and `announced_deadline_for` therefore announces nothing; a clock-reading
  branch in a read handler would change nothing about a turn, and the two entries agree.
- 2026-09-17: neither half has fired, and two statements here were narrower or wider than the
  tree. The recheck named only `session_servicer.py`, which holds two of the five methods the
  body's plan treats as repeatable reads (`ListSessions` and `GetSessionMessages`);
  `GetPreferences` is in `preference_servicer.py:34`, and `ListDueReminders` and `Health` are in
  `server.py:193` and `:127`. The trigger now greps the whole package, and that grep lists only
  `abandon.py`. That grep also never answered the first half, since it reports whether this entry
  was built rather than whether a read was measured, so the first half now has its own command. The 2026-09-11 line said no `perf_counter`, `time.monotonic` or `Instant::now`
  appears in any source file of either tree. That holds for production source and not for tests:
  21 test files read a monotonic clock, 19 Python and 2 Rust. Two of them touch a read, and
  neither times a served one. `test_fold_under_load_live.py` opens a `RedisSessionStore` and
  times GPU lease waits and model calls, and `body/crates/rpc/tests/live.rs:304` times a
  `list_sessions` against a peer that serves nothing, to measure the retry schedule. So the claim
  that no store read's duration is measured anywhere still holds. `ANNOUNCED_DEADLINE_GRACE_MS`
  is still 250 at `plan.rs:79`, still asserted as an equality at `retry_plan.rs:465`, and no
  commit since 2026-09-11 touched either file. The paging cursor
  ([184](184-paging-cursor.md)) is still open.
