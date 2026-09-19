# The cost row's assertions are the pick's saturation and the alt fails both

**Status:** done 2026-09-10
**Area:** inference
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

`test_what_this_corpus_costs_in_image_tokens_at_each_frame` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
asserted that a larger frame costs more image tokens at the shipped budget and exactly the same at
the engine's own. Both hold for the pick, whose corpus screen costs 629, 1010 and 1010 tokens at the
three frames under the shipped budget and 266 at all three under the engine's. Neither holds for the
alt, which costs 1010 at every frame under the shipped budget and 1402, 4082 and 4082 under the
engine's, so both of its rows failed.

Each failure is a fact rather than a defect in the measurement: at the shipped budget the alt is
already at the cap on the corpus frame, and at the engine's own budget its encoder does not discard
a larger frame's pixels the way the pick's does. What was wrong is where the facts are written. The
assertions read as though the saturation were a property of the measurement, and their messages tell
the reader the frame rows compare two deliveries of one picture, which is true of the pick at one
budget and of the alt at the other.

## History

- 2026-09-07: opened by the close of
  [R-586](586-the-cortex-alts-pixel-rows-are-undrawn-now-that-its-artifact-loads.md), which drew
  both of the alt's cost rows and recorded both failures.
- 2026-09-09: claims checked against the tree. The row still asserts `large > base` at the shipped
  budget and `large == base` at the engine's own, over every frame it renders, and both published
  cost tables are the ones quoted here. What was loose is the pointer to the rows this decision
  blocks: it read as a count of undrawn frame rows, where the rows the decision is about are the
  four at the doubled frame.
- 2026-09-10: done, and the row is now checked against the property both candidates share. One thing
  this entry says is loose: the pick's shipped row is not three costs that all differ, it is 629 at
  the corpus frame and 1010 at both larger frames, which is the cap. So all different is a property
  of each larger frame against the corpus frame rather than of the three costs pairwise, and that is
  also the only comparison the frame rows make. The row now prints every frame's cost and sorts them
  with `frame_axis` into one of two readings, one picture at every frame or more picture at every
  larger frame, and asserts only that the row is in one of them. What fails is a row where one
  larger frame is more picture and another is the same picture, which no account of the frame axis
  covers. Which reading each candidate is in is recorded in
  [ADR-0041 decision 18](../../adr/ADR-0041-injection-image-variant.md): the pick is more picture at the
  shipped budget and one picture at the engine's own, the alt the reverse at each, so the two
  candidates are in opposite readings at both budgets. What an alt frame row measures at each budget
  is written there and in the [llamacpp-gpu runbook](../../runbooks/llamacpp-gpu.md)'s vision
  section, where an operator reads it: at the shipped budget it is not a frame comparison, since the
  alt is at the cap on the corpus frame and its larger frames differ only in the resampling behind
  the same 1010 tokens. The sort is checked CI-side against the four published tables and a
  saturating pair, and three mutants over it fail those rows.
