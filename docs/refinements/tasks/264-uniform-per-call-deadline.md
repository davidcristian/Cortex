# A uniform per-call deadline on `BodyService`

**Status:** landed 2026-08-18
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Capture is the first call to carry one
(`CORTEX_BODY_CAPTURE_TIMEOUT_S`), because a blit plus an encode is the first that can park a
host thread. `get_volume`, `set_volume`, and `notify` keep their live-validated no-deadline
behaviour; changing what works is not a change this slice earned.

## Trail

- 2026-07-18: recorded in this area when the vision slice landed, one of four vision entries the
  index grouped in its fix-when-it-bites bucket with the trigger its own entry implies. The index
  dates that grouping only as "the same day" beside a paragraph about entries that had no bucket
  line until 2026-07-19, so which of the two days it means is not settled there.
- 2026-08-09: covered by the trigger sweep that ran against the tree over the whole fix-when-it-bites
  bucket and fired nothing. The index recorded that sweep so the next reader would spend the pass
  elsewhere instead of re-deriving the same verdicts, and it read every entry in the bucket against
  the code rather than against the entry's own text.
- 2026-08-18: Landed, and the entry's own two premises are what closed it, both being wrong rather
  than expired. The body's `off_worker` doc says every handler runs on `spawn_blocking` because
  Core Audio and the toast manager are COM and a COM call can park its thread for as long as the
  host takes, so all four calls park one and capture is merely the slowest; and the
  "live-validated" behaviour the deferral protected does not exist, all three host validations of
  the real backends being `never attempted`. So the trigger this entry was waiting for had already
  fired on the day it was written. Measured rather than argued: with no deadline, a call to a
  loopback port with nothing listening takes 20 seconds to fail (grpc's connect backoff) and a
  wedged handler never fails at all, nothing above the gateway bounding a tool call.
  `CORTEX_BODY_CALL_TIMEOUT_S` (5.0) now bounds the other three, capture keeps its own 10.0
  because the two calls really do differ, both defaults are declared once in the adapter that
  spends them and imported by `BodyConfig`, which moved to `config_body.py` at `config.py`'s line
  cap. The Rust side's deadline trap was checked for here and is absent: grpc-python spends
  `DEADLINE_EXCEEDED` for its own expiry, which already classified as `UNREACHABLE`, and that is
  now pinned by test rather than inherited. Opened
  [R-308](308-crosscheck-cannot-tie-a-decimal.md), the deadline defaults being spelled in the
  brain and again in compose with a cross-tree scan that cannot compare a decimal.
