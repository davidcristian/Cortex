# The capture time test fails when the wall clock steps back during it

**Status:** open, actionable
**Area:** rpc-transport
**Origin:** [ADR-0002](../../adr/ADR-0002-toolchain-checks.md)
**Verified:** 2026-11-25

`capture_screen_returns_a_real_downscaled_png_with_its_source_size`
(`body/crates/rpc/tests/body_server.rs`) asserts that the capture's `captured_at_unix_ms` lies
between two `SystemTime` readings taken before and after the call. The wall clock is not
monotonic: during a `just check` on 2026-11-25 the clock of the WSL machine stepped back while the
test ran, the reading taken after the call was 911 ms earlier than the one taken before it, and
the test failed with `1795599873080 is not between 1795599873992 and 1795599873081`. The same
commit passed on the next run, with no change.

What would close it: a check of the capture time that a backward clock step cannot fail, such as
a clock the test supplies to the screen service, or a bound on the distance from a reading taken
after the call; proved by a test whose clock steps back between the two readings.

## History

- 2026-11-25: filed from a failed `just check` in the third audit of the night, whose log is
  `commit1.log` in `~/.cache/cortex-run/2026-11-25/a3/`.
