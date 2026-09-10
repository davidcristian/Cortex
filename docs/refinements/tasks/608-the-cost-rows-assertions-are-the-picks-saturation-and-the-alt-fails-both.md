# The cost row's assertions are the pick's saturation and the alt fails both

**Status:** landed 2026-09-10
**Area:** inference
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

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
- 2026-09-10: **landed, and the row is held to the property both candidates share.** Re-derived
  first. The two assertions read as this entry describes them and all four published cost tables
  hold, and one thing this entry says is loose: the pick's shipped row is not three costs that all
  differ, it is 629 at the corpus frame and 1010 at both larger frames, which are the cap. So "all
  different" is a property of each larger frame against the corpus frame rather than of the three
  costs pairwise, and that is also the only comparison the frame rows make, since a row at one frame
  is read against the row at the corpus frame and no row compares the doubled frame with the third.
  The row now prints every frame's cost and sorts them with `frame_axis` into one of two readings,
  one picture at every frame or more picture at every larger frame, and asserts only that the row is
  in one of them. The shape that fails is a row where one larger frame is more picture and another
  is the same picture, which no account of the frame axis covers. Which reading each candidate is in
  is recorded in the
  [ADR-0029 frame-axis addendum](../../adr/ADR-0029-vision-screen-capture.md): the pick is more
  picture at the shipped budget and one picture at the engine's own, the alt the reverse of that at
  each, so the two candidates are in opposite readings at both budgets. What an alt frame row
  measures at each budget is written there and in the
  [llamacpp-gpu runbook](../../runbooks/llamacpp-gpu.md)'s image-arm section, where an operator
  reads it: at the shipped budget it is not a frame comparison, since the alt is at the cap on the
  corpus frame and its larger frames differ only in the resampling behind the same 1010 tokens. The
  sort is held CI-side to the four published tables and to a saturating pair, and three mutants over
  it fail those rows.
