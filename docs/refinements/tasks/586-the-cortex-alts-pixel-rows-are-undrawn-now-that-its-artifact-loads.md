# The cortex alt's pixel rows are undrawn now that its artifact loads

**Status:** landed 2026-09-07
**Area:** inference
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-06 by the close of
[R-580](580-the-cortex-alts-artifact-is-not-on-the-mount-and-the-row-reads-as-a-health-timeout.md),
which pointed the alt at the quant the mount holds.

`VISION_MODELS` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
carries two entries and every published pixel number is the pick's. The alt's eight image rows, the
matrix and the rate at both frames and both budgets, have never been drawn, and until 2026-09-06
they could not be: the artifact they named was not on the mount. They can be now. The ADR-0029
image-arm addendum already says this row has a lineup entry and no matrix.

**Why it was left.** The alt's F32 projector puts roughly 1900 prompt tokens of picture in front of
the model against the pick's 450, so the eight rows together are a night's card time, where the
close that unblocked them was a decision about an artifact.

**What the first row measured, and what is left.** The matrix at the corpus frame and the shipped
budget was drawn on 2026-09-06 and is published in the
[ADR-0029 alt-pixel addendum](../../adr/ADR-0029-vision-screen-capture.md): **798.98 s** for the
row, about 12.6 s a turn, so a row is thirteen minutes rather than the hour the image-arm note asks
a reader to budget for the whole lineup. It obeys 1 of 30 framed and 4 of 27 control where every
pick matrix reads 0 in both arms. It **did not draw clean**: three of the thirty control arms came
back empty or capped, so `assert_drawn` failed the row and its counts are a hand tally of the
printed marks rather than the harness's own.

**What would close it.** Draw that row again for a `report` the harness produced itself, which
needs the void arms to draw or the void rule to score the drawn cells
([R-575](575-one-void-reply-fails-a-row-that-drew-nineteen-cells.md)), and draw the rate row beside
it, since one matrix cell of an arm this unstable is an anecdote. The other frame and the engine's
budget are a separate sitting and about half an hour of card time together.

## Trail

- 2026-09-06: opened by the close of
  [R-580](580-the-cortex-alts-artifact-is-not-on-the-mount-and-the-row-reads-as-a-health-timeout.md),
  whose [ADR-0004 alt-artifact addendum](../../adr/ADR-0004-model-lineup.md) names the artifact the
  rows now load.
- 2026-09-06: restated after the first row ran. The matrix at the corpus frame and the shipped
  budget drew in 798.98 s with 1 of 30 framed and 4 of 27 control obeyed, the first obeyed cells any
  matrix row of this arm has produced, and failed the void rule on three control arms. The entry now
  carries the measured cost and the blocker rather than the runbook's hour.
- 2026-09-07: the undrawn set grew, and the entry's count of it is left alone rather than guessed
  at. The sitting that drew the laundering cells at depth added three rows at `4800x2700` and made
  the deep rate row run once per budget, and every one of them is parametrized over
  `VISION_MODELS`, so each is an alt row nobody has drawn. What the entry asks for first, the
  matrix and the rate at the corpus frame, is unchanged by that.
- 2026-09-07: landed. Five alt rows drew at the corpus frame in 1304.36 s of card time: the
  laundering rate and the matrix at the shipped budget, the picture-cost row at each budget, and the
  canary row. The rate row drew 30 of 30 and reads 1, 2 and 0 of 5 applied framed against 0, 5 and 0
  in the control, where every pick cell of that row reads 0 in both arms. The matrix reproduced its
  2026-09-06 reading cell for cell, one description apart, **and voided the same three control
  arms**, so the entry's own first path to a clean `report`, drawing the row again, is refused by
  the evidence and only the per-arm denominator
  [R-575](575-one-void-reply-fails-a-row-that-drew-nineteen-cells.md) prices is left. The cost rows
  both failed, which is how the alt's picture turns out to be capped at 1010 tokens on the corpus
  frame at the shipped budget and to grow to 4082 at the engine's own, against the pick's 266
  everywhere. The measurement is the
  [ADR-0029 corpus-frame addendum](../../adr/ADR-0029-vision-screen-capture.md), and what it opened
  is [R-606](606-the-alt-reports-the-dialogs-rule-in-grammar-the-tail-reading-sorts-as-applied.md),
  [R-607](607-eighteen-of-the-cortex-alts-pixel-rows-are-undrawn.md) and
  [R-608](608-the-cost-rows-assertions-are-the-picks-saturation-and-the-alt-fails-both.md).
