# The whole-subtask figure out by a factor of two

**Status:** done 2026-08-25
**Area:** resource-governance
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

"A whole CPU subtask measures 200 to 300 s" appears in the subagents runbook, in the stall ceiling's
derivation and in the admission wait's, where it is multiplied out into the 900 s and 1800 s waits
the 3600 s bound is twice. Measured on the shipped entry at the compose file's own shape, it holds
for an extraction (410.5 s is already above it) and is out by a factor of two for a summarization
(623.8 s), which is the shape delegation is most often for. Neither bound derived from it is wrong in
the direction that matters, both being deliberately generous and both bounding a failure rather than
pacing normal work, but a bound whose derivation no longer matches the machine cannot be retuned with
confidence.

## History

- 2026-08-11: Opened by the total generation cap's close, whose measurements say so.
- 2026-08-25: Closed. The figure was measured again from a full `MAX_SPAWN_BATCH` driven through the
  real chain against a live CPU entry at the compose file's own shape, in both placement regimes, and
  it becomes an interval rather than a point: a whole subtask reads 222.8 to 324.3 s across the eight
  runs taken one after another on a quiet box, against the 623.8 s of the single-subtask table. So
  the runbook's 200 to 300 s was very nearly right and the correction asked for is a widening rather
  than a shift. The measurement also found what the entry could not: a spawn holds its admission for
  longer than it runs, queueing on the roster entry's model lease inside its own admission, up to
  595.2 s, and it is that hold the run deadline bounds. Both bounds are confirmed rather than
  retuned, the deadline reaching 2400 s by two independent routes and the wait's arithmetic reading
  1624.6 s and 893.2 s against its predicted 1800 s and 900 s. The runbook, the two module contracts
  and the two code comments now use the interval. It opened
  [R-430](430-the-bounds-are-sized-on-an-idle-box.md), from the control run beside the batch, where
  the same subtask on a saturated host takes 1736.6 s, five to eight times the quiet reading and
  within 28% of the run deadline; and [R-431](431-the-token-cap-fires-on-the-shape-that-ships.md),
  where on the tool-less shape the compose override actually ships, the same subtask ran to the
  1024-token cap and came back a refusal.
