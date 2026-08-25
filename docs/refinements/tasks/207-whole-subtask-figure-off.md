# The whole-subtask figure out by a factor of two

**Status:** landed 2026-08-25
**Area:** resource-governance
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

The whole-subtask figure two derivations rest on is out by a factor of two.
Opened 2026-08-11 by the close above, whose measurements are what say so. "A whole CPU
subtask measures 200 to 300 s" appears in the subagents runbook, in the stall ceiling's
derivation and in the admission wait's, where it is multiplied out into the 900 s and 1800 s
waits the 3600 s bound is twice. Measured on the shipped entry at the compose file's own shape,
it holds for an extraction (410.5 s is already above it) and is out by a factor of two for a
summarization (623.8 s), which is the shape delegation is most often for. Neither bound derived
from it is *wrong* in the direction that matters, both being deliberately generous and both
bounding a failure rather than pacing normal work, but the arithmetic under the admission wait
now understates its own inputs, and a bound whose derivation no longer matches the machine is a
bound nobody can retune with confidence. **The trigger is the first spawn observed refused at the
admission bound**, or a retune of either bound for any other reason, at which point the figure is
re-derived from a batch rather than from single subtasks; that is the measurement this entry is
really waiting on, since the queue's arithmetic is about a batch's serialization and these five
runs were one at a time.

## Trail

- 2026-08-11: Opened by the total generation cap's close, whose measurements on the shipped entry
  are what say so. An extraction at 410.5 s is already above the 200 to 300 s figure and a
  summarization at 623.8 s is out by a factor of two, which is the shape delegation is most often
  for.
- 2026-08-25: Landed. The figure was re-measured from a full `MAX_SPAWN_BATCH` driven through the
  real chain against a live CPU entry at the compose file's own shape, in both placement regimes,
  and it becomes an interval rather than a point: a whole subtask reads 222.8 to 324.3 s across the
  eight serialized runs on a quiet box, against the 623.8 s of the single-subtask table this entry
  was opened by. So the runbook's 200 to 300 s was very nearly right today and the correction this
  entry asked for is a widening, not a shift. The re-derivation also found what the entry could not
  have: a spawn holds its admission for **longer than it runs**, queueing on the entry's model
  lease inside its own admission, up to 595.2 s serialized, and it is that hold the run deadline
  bounds. Both bounds are confirmed rather than retuned by the batch, the deadline landing on
  2400 s by two independent routes and the wait's own arithmetic reading 1624.6 s serialized and
  893.2 s overlapping against its predicted 1800 s and 900 s. Recorded in the ADR-0005 batch
  addendum with both tables; the runbook, the two module contracts and the two code comments now
  carry the interval. What it opened is
  [R-430](430-the-bounds-are-sized-on-an-idle-box.md), from the control run beside the batch: the
  same subtask on a saturated host takes 1736.6 s, five to eight times the quiet reading and within
  28% of the run deadline, so the interval has a cause and every bound here is sized on its fast
  end. The constrained control opened a second,
  [R-431](431-the-token-cap-fires-on-the-shape-that-ships.md): on the tool-less shape the compose
  override actually ships, the same subtask ran to the 1024-token cap and came back a refusal.
