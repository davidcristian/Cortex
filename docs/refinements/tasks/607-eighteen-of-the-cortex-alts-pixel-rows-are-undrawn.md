# Twenty of the cortex alt's twenty-five pixel rows are undrawn

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-09

Opened 2026-09-07 by the close of
[R-586](586-the-cortex-alts-pixel-rows-are-undrawn-now-that-its-artifact-loads.md), which drew the
alt's rate, matrix, cost and canary rows at the corpus frame.

Every row of the image arm in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
is parametrized over `VISION_MODELS`, which carries the pick and the alt, so the arm holds
twenty-five alt rows. Five are drawn: the matrix and the laundering rate at the corpus frame and
the shipped budget, the picture-cost row at each budget, and the canary row. The other twenty are
these:

- the matrix and the rate at the doubled frame, and both of them at the engine's own budget, six
  rows;
- the payload-size sweep, four rows, one per frame and budget;
- the matrix, the rate and the sweep at the third frame, three rows;
- both budgets' deep rows at a hundred and twenty draws an arm, two rows;
- the `plain` cell's two deep rows, 280 draws an arm at the corpus frame and 120 at the third
  frame, two rows;
- the dialog cell's twenty framed draws, the square's four corners, and the dialog pair at the
  falling size, three rows.

**Why it was left.** The sitting that drew the five had fifty minutes of card time and spent them on
the rows the pick publishes at the corpus frame, which is what makes the two candidates comparable
at all. The alt costs about 12 s a turn against the pick's 2.3, measured over the 96 turns of this
sitting's two long rows, so the six frame and budget rows are about an hour together and each of
the two 120-draw deep rows, 720 replies apiece over three renderings, is over two hours. The two
`plain` rows added on 2026-09-08 draw one cell each, 560 replies and 240, which is about two hours
and about fifty minutes at that rate; the second is drawn at the engine's own budget, where the
alt's picture is four times the size the 12 s was measured on.

**What would close it.** Draw them in the order the questions were asked of the pick: the frame and
budget rows first, then the sweep, then the deep rows, which at this candidate's speed are a sitting
each. Two of them need a decision before they are worth card time, and the cost rows are why: at the
shipped budget the alt's three frames all arrive as 1010 image tokens, so its frame rows there
compare three deliveries of one picture, and at the engine's own budget its frames really differ,
where the pick's do not. Whatever those rows measure for the alt, it is not what the pick's rows of
the same name measure
([R-608](608-the-cost-rows-assertions-are-the-picks-saturation-and-the-alt-fails-both.md)). Each row
that lands takes its line out of the list above, and the entry closes when the list is empty.

## Trail

- 2026-09-07: opened by the close of
  [R-586](586-the-cortex-alts-pixel-rows-are-undrawn-now-that-its-artifact-loads.md), whose
  [ADR-0029 corpus-frame addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes the five
  rows that are drawn.
- 2026-09-09: claims held to the tree, and the counts had moved. Collecting the image arm reports
  25 alt rows where the entry says 23, because two rows drawing the `plain` cell deep landed on
  2026-09-08, the day after this was opened, and neither was drawn for the alt. The five drawn rows
  are still the five. The file keeps its name, which spells the old count.
