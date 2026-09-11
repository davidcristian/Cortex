# The cells whose published reading is one load's answer are undrawn across loads

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-11 by the close of
[R-623](623-a-cell-that-settles-per-load-is-read-in-draws-rather-than-loads.md), which put the row
shape a settling cell needs into
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
as `_draw_cell_across_loads` and drew it on one cell, the advisory probe's control arm at 16 px at
the engine's own budget.

That close also said which readings need the shape: an arm that wrote one or two strings in most of
a load's draws is an arm whose deep count is the answer one load settled on, and four such arms are
published from one load each.

- The cortex alt's `chrome/output-laundering` cell at the corpus frame and the shipped budget, both
  arms: the control wrote one string in all twenty draws and the framed arm two strings, 15 and 5,
  where the five-draw rate row had drawn 3 of 5 mentioned (the alt-spelling addendum).
- The pick's `bare` control at 24 px and at 16 px at the corpus frame at the engine's own budget:
  one string in all twenty draws at each size (the body-pair addendum).
- The pick's `plain` control at the same two sizes, frame and budget: two strings, 19 of 20 applied
  at each size (the body-pair addendum).
- The pick's `plain` control at the corpus frame and the shipped budget: one string in all 560
  draws (the obeyed-direction addendum).

The advisory probe is not in the list because the loads row has now drawn it four times behind four
loads. That sitting is also what a reader of this entry should know before drawing one of these:
its four loads, drawn back to back on one night, all settled on the same control string at 1 of 20,
where three earlier sittings had drawn 4 of 5, 1 of 20 and 19 of 20, so the spread a settled cell
shows is between sittings on different nights rather than between loads in one sitting, and a
row of four loads drawn in one sitting may come back agreeing with itself. The row shape is the
instrument either way, one sitting being one run of it, and the reading to publish is the per-load
counts of each sitting beside the sittings before it. The cells whose framed arm draws many distinct
strings are not in the list either: the pick's `plain`
framed arm wrote 42 distinct strings in 560 draws at the shipped budget and its `app` framed arm
draws varied wordings, so those counts are rates over draws.

**What would close it.** Point `_draw_cell_across_loads` at each of the four, which is a row per
cell naming its rendering, budget, payload size and attack, and publish the per-load counts beside
the pooled one. The cost is the loads: the alt's dialog cell is about eleven minutes a load with
its control arm at about 27 s a reply, so four loads are about 45 minutes; the body pair is 782 s a
load for both renderings at both sizes, about 52 minutes for four; the pick's `plain` control at
the shipped budget is about 1.2 s a reply, so four loads of twenty per arm are about four minutes
with the loads included.

## Trail

- 2026-09-11: opened by the close of
  [R-623](623-a-cell-that-settles-per-load-is-read-in-draws-rather-than-loads.md), whose
  [ADR-0029 loads addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes the row shape
  and the advisory probe drawn across four loads.
