# A uniform per-call deadline on `BodyService`

**Status:** done 2026-08-18
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Capture was the first call with a deadline (`CORTEX_BODY_CAPTURE_TIMEOUT_S`), because a blit plus
an encode is the first that can park a host thread. `get_volume`, `set_volume` and `notify` kept
their no-deadline behaviour at the time.

## History

- 2026-07-18: Recorded when the vision slice was finished, as one of four vision entries deferred
  until they cause a problem.
- 2026-08-09: A review of those entries against the code found that none had.
- 2026-08-18: Done, and both of the entry's premises turned out to be wrong rather than out of
  date, which is what closed it. The body's `off_worker` doc says every handler runs on
  `spawn_blocking` because Core Audio and the toast manager are COM and a COM call can park its
  thread for as long as the host takes, so all four calls park one and capture is merely the
  slowest; and the "live-validated" behaviour the deferral protected does not exist, since all
  three host validations of the real backends were never attempted. So the trigger had already
  occurred the day the entry was written. Measured rather than argued: with no deadline, a call to
  a loopback port with nothing listening takes 20 seconds to fail (grpc's connect backoff) and a
  stuck handler never fails at all, with nothing above the gateway bounding a tool call.
  `CORTEX_BODY_CALL_TIMEOUT_S` (5.0) now bounds the other three, capture keeps its own 10.0, and
  both defaults are declared once in the adapter that uses them and imported by `BodyConfig`, which
  moved to `config_body.py` at `config.py`'s line cap. The Rust side's deadline problem was checked
  for here and is absent: grpc-python raises `DEADLINE_EXCEEDED` for its own expiry, which already
  classified as `UNREACHABLE`, and a test asserts that now. Opened
  [308](308-crosscheck-cannot-tie-a-decimal.md), since the deadline defaults are written in the
  brain and again in compose, and the cross-tree check cannot compare a decimal.
