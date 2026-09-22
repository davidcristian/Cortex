# Only the corpus laundering cell is drawn at the engine's sampler

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)
**Verified:** 2026-09-22

Every framed count in [injection over pixels](../../readings/injection-over-pixels.md) outside the
laundering cell at the corpus frame and size was drawn at temperature 0 beside a control drawn the
same way. There a control's prompt is the same bytes in every draw and has one answer, while the
framed count is a rate over the fence's nonce, and up to 2026-09-19 the prompt cache also made a
control's later draws a second computation. So only that cell compares two rates. Two of ADR-0041's
consequences still read a direction off a one-answer control: plain framed at 4800x2700 on the
engine budget, and the alt's 9 of 280 on its plain cell.

The cells, in the order those consequences need them:

- the mail cell at the shipped budget, pick, at the row's 400 draws per condition
  (`_MAIL_RUNS`): at 120 it read framed 7 against control 1 by hand, the one cell where the framed
  count is above the control's, and not apart at that depth;
- `plain` at 4800x2700 on the engine budget, pick;
- the alt's `plain` cell at the shipped budget;
- the five-draw and six-draw cells at the doubled and third frames, the payload-size table, the
  probe screens (`advisory`, `bare` and `chrome` at 16 px), the matrices, and the alt's other
  controls, among them the mail control whose one answer ran to the end of the window
  ([R-695](695-an-alt-mail-control-voids-in-every-draw-at-the-engine-budget.md)).

**Cost.** On 2026-09-22 the pick's corpus cell took about 12 minutes at the shipped budget and 19 at
the engine budget for 120 draws per condition, with the clock at a median 0.61 and 0.60 of the
card's maximum SM clock; a row's total is in the readings.

**What would close it.** Each listed cell drawn in both conditions with the rows as they now are,
which sample as the shipped request does and evaluate the whole prompt; the readings restated with
the new counts in place of the temperature-0 ones, and ADR-0041's consequences edited where a
direction changes. A control count alone closes no cell, since the framed count beside it was drawn
at temperature 0. Every reply is read by hand, `desc` replies included, under ADR-0041's decision
11.

## History

- 2026-09-22: opened by the close of
  [R-696](696-the-first-draw-on-a-server-differs-from-the-rest.md), which found the prompt cache
  made a control's later draws a second computation and drew the corpus cells again whole.
