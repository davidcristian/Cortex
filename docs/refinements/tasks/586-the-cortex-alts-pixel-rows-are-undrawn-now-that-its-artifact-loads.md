# The cortex alt's pixel rows are undrawn now that its artifact loads

**Status:** done 2026-09-07
**Area:** inference
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

`VISION_MODELS` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
has two entries and every published pixel number is the pick's. The alt's eight image rows, the
matrix and the rate at both frames and both budgets, had never been drawn, and until 2026-09-06 they
could not be, since the artifact they named was not on the mount. The alt's F32 projector puts
roughly 1900 prompt tokens of picture in front of the model against the pick's 450, so the eight
rows together are a night of card time.

## History

- 2026-09-06: opened by the close of
  [R-580](580-the-cortex-alts-artifact-is-not-on-the-mount-and-the-row-reads-as-a-health-timeout.md),
  whose 2026-09-06 change of artifact ([ADR-0004](../../adr/ADR-0004-model-lineup.md)) names the
  artifact the rows now load.
- 2026-09-06: restated after the first row ran. The matrix at the corpus frame and the shipped
  budget drew in 798.98 s, about 12.6 s a turn, with 1 of 30 framed and 4 of 27 unframed obeyed, the
  first obeyed cells any matrix row of this kind has produced, and failed the void rule on three
  control replies, so its counts are a hand tally of the printed marks. The entry now has the
  measured cost and the blocker rather than the runbook's hour.
- 2026-09-07: the undrawn set grew. The session that drew the laundering cells at depth added three
  rows at `4800x2700` and made the deep rate row run once per budget, and every one is parametrized
  over `VISION_MODELS`, so each is an alt row nobody has drawn.
- 2026-09-07: done. Five alt rows drew at the corpus frame in 1304.36 s of card time: the laundering
  rate and the matrix at the shipped budget, the picture-cost row at each budget, and the canary
  row. The rate row drew 30 of 30 and reads 1, 2 and 0 of 5 applied framed against 0, 5 and 0
  unframed, where every pick cell of that row reads 0 in both conditions. The matrix reproduced its
  2026-09-06 reading cell for cell, one description apart, and voided the same three control cells,
  so drawing the row again cannot produce a clean `report` and only the per-condition denominator
  [R-575](575-one-void-reply-fails-a-row-that-drew-nineteen-cells.md) prices is left. Both cost rows
  failed, which is how the alt's picture turns out to be capped at 1010 tokens on the corpus frame
  at the shipped budget and to grow to 4082 at the engine's own, against the pick's 266 everywhere.
  The measurement is [ADR-0041 decision 4](../../adr/ADR-0041-injection-image-variant.md), and it opened
  [R-606](606-the-alt-reports-the-dialogs-rule-in-grammar-the-tail-reading-sorts-as-applied.md),
  [R-607](607-eighteen-of-the-cortex-alts-pixel-rows-are-undrawn.md) and
  [R-608](608-the-cost-rows-assertions-are-the-picks-saturation-and-the-alt-fails-both.md).
