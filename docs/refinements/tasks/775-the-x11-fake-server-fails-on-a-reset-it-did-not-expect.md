# The X11 test server fails on a reset it did not expect

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-10-02

`an_x_error_while_listing_windows_is_a_failed_grab_that_releases_the_server` in
`body/crates/os_linux/tests/x11.rs` fails about one run in fifty, and with it `just check`. The
fake server's thread panics at the `read_to_end` that ends `serve` with
`Os { code: 104, kind: ConnectionReset }`, and the test then panics at its `server.join()`.
Measured on 2026-10-02 with the debug test binary under `taskset -c 0-11`: 2 of 200 runs of the
test alone failed, and 3 of 100 runs of the whole `x11` suite.

The likely cause, not yet confirmed: in the `at_a_window` case the server answers the client's
pipelined requests after the `GetWindowAttributes` error, and when the client drops the
connection before reading those answers, a Unix socket closed with unread data reports a reset to
its peer instead of an end of stream. Whether the client has read them first depends on timing.

The fix has a constraint: `cargo llvm-cov` runs over `--all-targets`, so a branch in `serve` that
accepts a reset and is reached only when the race occurs would make the Rust coverage check fail
in the same runs. A fix that removes the race, such as having the server stop writing once the
test's answer list says the client gave up, keeps every branch reached on every run.

## History

- 2026-10-02: Opened by the review of
  [R-336](336-packed-values-keep-their-whole-length.md),
  [R-343](343-a-userinfo-the-pattern-cannot-reach.md) and
  [R-471](471-the-lines-ceiling-is-the-least-sampled-cohort.md), whose first `just check` failed on
  this test with no change under `body/`.
