# The whole-subtask figure out by a factor of two

**Status:** open, fix when it bites
**Area:** resource-governance
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** The first spawn observed refused at the admission bound, or a retune of either bound.

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
