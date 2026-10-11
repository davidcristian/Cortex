# A clipboard test reaches one of two error paths by a race

**Status:** done 2026-10-11
**Area:** repo-checks
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)

`a_server_that_closes_before_the_property_fails_the_read` in
`body/crates/os_linux/tests/selection.rs` ends its script with `Step::Hangup`, which closes the
fake X server's socket right after it pushes the `SelectionNotify`. The client then either reads
the event and fails in `X11Selection::take`, where `get_property` meets the closed socket, or
fails earlier in `wait`, whose `flush` or `poll_for_event` meets it first. Both give
`SelectionError::Failed`, so the test passes either way, but no other test reaches the error
return of the `?` after `Cookie::reply` in `take`. A run where the race goes to `wait` reports
that one region as not covered, and `just check` fails on `check-body`.

Seen on 2026-10-10: the same tree passed `just check` twice in the pre-commit hook and then
failed once with `FAIL regions: 99.99% (need 100%)`, the one region being
`selection.rs` line 208 (`.map_err(ReplyOrIdError::from)?`, count 0), while the `?` on line 180
had the count the `wait` path gives.

## What to do

Make the test reach `take`'s error every time: add a step that reads one request and then closes
without answering, and end this test's script with it, so the server closes only after the client
has sent `GetProperty`. Check that `a_server_that_closes_between_chunks_fails_the_read` still
reaches `wait`'s error on its own, then run `just check-body` several times.

## History

- 2026-10-10: filed from the run's last `just check`.
- 2026-10-11: done. x11rb discards the packets it reads in the same call that meets the end of
  the stream, so at idle this test failed in `wait` in 3 of 3 runs alone, and
  `a_server_that_closes_between_chunks_fails_the_read`, which had the same shape, failed in the
  first `take` instead of the chunk loop and covered the region by chance. Both scripts now read
  the client's `GetProperty` before they close, with the existing `Step::Answer(Vec::new())` and
  `Step::Hangup` rather than a new step, and assert that request. Coverage runs of the selection
  test beside 48 busy loops: before, 1 of 36 left the region uncovered (0 of 20 idle); after, 24
  of 24 covered it, from both tests each run. `a_server_that_closes_mid_read_fails_it` reaches
  `wait`'s error with nothing unread; the other early closes in this file and in `keys.rs` follow
  nothing written, and `x11.rs` already reads a request before it closes.
