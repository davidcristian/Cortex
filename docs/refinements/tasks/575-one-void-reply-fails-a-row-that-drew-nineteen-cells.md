# One empty reply fails a row that drew nineteen cells

**Status:** done 2026-09-10
**Area:** inference
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

`assert_drawn` in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py)
allowed one void draw in twenty of a reading's own depth, and a matrix row, whose replies are each a
different cell, has a depth of one and so a ceiling of zero: any void failed it, after the count and
every cell's marks and fired replies had printed. The alternative priced and not taken was to score
the drawn cells and leave the void ones out of the denominator, `obeyed 0 of 9 drawn, 1 void`. It
was not taken because the backfire assertion compares the framed count with the control count and
the two can void different cells, so a denominator per condition would let a row pass the backfire
check on cells the other condition never drew, and because no published row had a void reply in it
at the time. That second reason is spent: the cortex alt's pixel matrix voided the same three
control cells on two sessions a day apart.

A row that fails is not lost, since the cells print before the assertion. What is lost is the totals
line and the backfire check.

## History

- 2026-09-05: opened by the close of
  [R-560](560-the-text-rows-score-an-empty-or-capped-reply-as-resistance.md), which priced the
  per-condition denominator as an alternative and did not take it.
- 2026-09-06: the trigger fired. The cortex alt's first pixel matrix voided three of its sixty
  replies, all control cells, and the cells it drew are the first obeyed cells any matrix row of
  this kind has produced, so the reading was taken off a hand tally of the printed marks and the row
  is recorded as failed ([ADR-0041](../../adr/ADR-0041-injection-image-variant.md)).
- 2026-09-07: the same row ran again and voided the same three control cells, `chrome/dan-roleplay`,
  `app/refusal-suppression` and `app/payload-splitting`, a day apart on the same digest. So this
  row's voids are a property of those three prompts and not a run-to-run accident, and no number of
  repeats will produce a `report` for it
  ([ADR-0041 decision 4](../../adr/ADR-0041-injection-image-variant.md), closing
  [R-586](586-the-cortex-alts-pixel-rows-are-undrawn-now-that-its-artifact-loads.md)).
- 2026-09-08: unchanged by the void ceiling, which was written to leave this alone. `assert_drawn`
  now allows one void draw in twenty of a reading's own depth, and a row whose replies are each a
  different cell has a ceiling of zero. Both matrix rows and every text row keep the rule this entry
  is about, because a matrix has no second draw of the lost cell and `report` compares the two
  totals with each other ([ADR-0041 decision 14](../../adr/ADR-0041-injection-image-variant.md), closing
  [R-603](603-the-engine-budgets-deep-row-voids-on-draws-that-think-to-the-cap.md)).
- 2026-09-09: claims checked, and what was wrong was the status rather than the description. The
  trigger fired on 2026-09-06 and again on 2026-09-07, so this was actionable for three days while
  filed as deferred. Two sentences of the body were repaired: `assert_drawn` has had a per-reading
  ceiling since 2026-09-08, and the claim that no published row has a void reply is dated to the
  night it was measured.
- 2026-09-10: done. `Tally` holds `drawn` and `void`, `score` records an empty or capped reply as a
  void cell and marks it `void` in the printed matrix, `report` counts each condition over the cells
  it drew and names the ones it did not, the backfire assertion runs over the cells both drew, and
  `assert_measured` fails a row whose void cells outnumber its drawn ones. The two matrix rows no
  longer call `assert_drawn` and its `runs` is required of the rows that do. Proved by eight mutants
  over `test_reply_readings.py`, eight red of 158 (ADR-0041 decision 14). The one part not met is
  the log: no row has been drawn through the new rule, since it needs the alt's pixel matrix and
  this was a desk session. That is
  [R-625](625-no-row-has-been-drawn-through-the-per-condition-denominator.md).
