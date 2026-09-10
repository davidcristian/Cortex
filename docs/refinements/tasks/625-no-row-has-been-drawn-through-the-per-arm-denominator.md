# No row has been drawn through the per-arm denominator

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-09-10

Opened 2026-09-10 by the close of
[R-575](575-one-void-reply-fails-a-row-that-drew-nineteen-cells.md), which changed what a matrix
row reports when an arm voids a cell and proved the new rules by mutation rather than by a row.

`report` now counts each arm over the cells that arm drew, names the cells it did not, holds the
backfire check to the cells both arms drew, and fails only when an arm's void cells outnumber its
drawn ones. Eight mutants over `test_reply_readings.py` say those rules can fail. What no file
here holds is a totals line a server produced: every void row this repo has published was read off
a hand tally of the printed marks, because the rule the row was failed by ran before `report` did.

The row that will draw it is the cortex alt's pixel matrix at the corpus frame and the shipped
budget, in
[test_injection_defense_live.py](../../../brain/packages/inference/tests/test_injection_defense_live.py).
It is the one row known to void: it lost the same three control arms, `chrome/dan-roleplay`,
`app/refusal-suppression` and `app/payload-splitting`, on two sittings a day apart on the same
digest, and it cost **867.50 s** of card time the second time (the ADR-0029 corpus-frame addendum).
Both of those sittings were hand tallied, so their numbers are what a `report` line off the third
sitting is checked against: 1 of 30 applied framed, 4 of 27 applied in the control. Those recorded
marks have been replayed through `score` and `report` with stand-in replies, and the line they print
is in the per-arm-denominator addendum, so what is missing is a server's own replies rather than the
shape of the line.

**What would close it.** Draw that row and publish what it printed at the ADR-0029 addendum that
reads the alt's matrix, against the two hand tallies: the per-arm denominators, the three named
void cells, and the count the backfire check compared over the cells both arms drew. A sitting that
lost different cells is worth as much, since which cells void is what the two hand tallies claim is
stable.

## Trail

- 2026-09-10: opened by the close of
  [R-575](575-one-void-reply-fails-a-row-that-drew-nineteen-cells.md), whose
  [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md) per-arm-denominator addendum records the
  decision, the mutation table behind it, and this as the clause of that close it did not meet.
