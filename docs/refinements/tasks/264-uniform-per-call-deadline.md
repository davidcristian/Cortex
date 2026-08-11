# A uniform per-call deadline on `BodyService`

**Status:** open, fix when it bites
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** A second `BodyService` call that can park a host thread.

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
