# The cost row's assertions are the pick's saturation and the alt fails both

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-09

Opened 2026-09-07 by the close of
[R-586](586-the-cortex-alts-pixel-rows-are-undrawn-now-that-its-artifact-loads.md), which drew the
alt's picture-cost row at each budget for the first time.

`test_what_this_corpus_costs_in_image_tokens_at_each_frame` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
asserts that a larger frame costs more image tokens at the shipped budget and exactly the same at
the engine's own. Both hold for the pick, whose corpus screen costs 629, 1010 and 1010 tokens at the
three frames under the shipped budget and 266 at all three under the engine's. Neither holds for the
alt, which costs 1010 at every frame under the shipped budget and 1402, 4082 and 4082 under the
engine's, so both of its rows fail.

Each failure is a fact rather than a defect in the measurement: at the shipped budget the alt is
already at the cap on the corpus frame, and at the engine's own budget its encoder does not discard
a larger frame's pixels the way the pick's does. What is wrong is where the facts are written. The
assertions read as though the saturation they hold were a property of the arm, and their messages
tell the reader the frame rows compare two deliveries of one picture, which is true of the pick at
one budget and of the alt at the other.

**Why it was left.** The sitting that drew the rows had the card for fifty minutes and spent it on
the readings the two candidates could be compared on. Deciding what this row asserts is a decision
about what the frame axis means per candidate, which is the same decision the alt's four undrawn
rows at the doubled frame need, the matrix and the rate at each budget
([R-607](607-eighteen-of-the-cortex-alts-pixel-rows-are-undrawn.md)), and taking it from one sitting
of one candidate would fix the row to the first artifact that broke it.

**What would close it.** Make the row report the costs and assert the property the arm really needs,
which is that a row's frames are either all the same picture or all different, and record which of
the two each candidate is in. Then say in the arm's own notes what an alt frame row measures at each
budget, since at the shipped budget it is not a frame comparison at all. The costs themselves are
already published in the
[ADR-0029 corpus-frame addendum](../../adr/ADR-0029-vision-screen-capture.md).

## Trail

- 2026-09-07: opened by the close of
  [R-586](586-the-cortex-alts-pixel-rows-are-undrawn-now-that-its-artifact-loads.md), which drew
  both of the alt's cost rows and recorded both failures.
- 2026-09-09: claims held to the tree. The row still asserts `large > base` at the shipped budget
  and `large == base` at the engine's own, over every frame it renders, and both published cost
  tables are the ones quoted here. What was loose is the pointer to the rows this decision blocks:
  it read as a count of undrawn frame rows, where the rows the decision is about are the four at
  the doubled frame.
