# The X11 test server fails on a reset it did not expect

**Status:** done 2026-10-02
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

`an_x_error_while_listing_windows_is_a_failed_grab_that_releases_the_server` in
`body/crates/os_linux/tests/x11.rs` failed about one run in a hundred, and with it `just check`.
The fake server's thread panicked either at the `read_to_end` that ends `serve`, with
`Os { code: 104, kind: ConnectionReset }`, or at the `write_all` of a reply, with
`Os { code: 32, kind: BrokenPipe }`, and the test then panicked at its `server.join()`. Measured on
2026-10-02 with the debug test binary under `taskset -c 0-11`: 2 of 200 runs of the test alone
failed, and 3 of 100 runs of the whole `x11` suite.

In the `at_a_window` case the grab sends four requests about one window at once, the server
answers the first with an error, and the grab stops reading there, releases the server and closes
its socket. The server still answered the other three. A reply written after that close fails with
a broken pipe. A reply written before it but after the grab's last read stays unread, and Linux
reports a Unix socket closed with unread data to its peer as a reset. Timing decided which.

The fix had a constraint: `cargo llvm-cov` runs over `--all-targets`, so a branch in `serve` that
accepts a reset and is reached only when the race occurs would make the Rust coverage check fail
in the same runs.

## History

- 2026-10-02: Opened by the review of
  [R-336](336-packed-values-keep-their-whole-length.md),
  [R-343](343-a-userinfo-the-pattern-cannot-reach.md) and
  [R-471](471-the-lines-ceiling-is-the-least-sampled-cohort.md), whose first `just check` failed on
  this test with no change under `body/`.
- 2026-10-02: Done. The flake is older than the fake server numbering its own replies: run alone
  under `taskset -c 0-11`, the test failed 15 of 4,000 runs on the tree before that change and 46
  of 4,000 after it. Sleeping 2 ms after each reply the server writes made 50 of 50 runs fail with
  a broken pipe, which places the cause in replies written after the grab stopped reading. The
  `at_a_window` script now answers the window's other three requests with nothing, so the server
  writes nothing after the error and the grab leaves nothing unread; under the same sleep it
  passed 50 of 50. Without it: 0 of 4,000 runs alone, 0 of 2,000 runs of the whole suite, and 0 of
  8,000 runs in eight parallel loops, where the old script failed 127 of 8,000. The test now also
  fails a grab that waits for those three replies before it fails, after the server's ten-second
  read timeout.
