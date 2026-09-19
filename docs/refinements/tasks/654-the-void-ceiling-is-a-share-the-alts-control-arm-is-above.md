# The empty-reply ceiling is a share the cortex alt's control condition is above

**Status:** done 2026-09-13
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

`assert_drawn` allows each reading, one condition of one cell, `runs // _VOID_SHARE` empty replies,
and `_VOID_SHARE` was 20. A rate row and a payload review draw `_RATE_RUNS`, which is 5, so their
readings had a ceiling of zero and one empty or capped reply failed the whole row. One in twenty was
set from the pick: its two deep rows at the engine's own budget lost 4 draws in 480, 0.83 in a
hundred, and the share is twice that.

The alt is above that share. Over the six rows drawn on 2026-09-12, 270 scored vision turns, its
control condition returned 15 empty replies in 135 draws, **11.1 in a hundred with 6.9 to 17.5
around it**, against 1 in 135 in the framed condition. Six of the fifteen are one mail cell that
answered nothing in six draws of six; setting that cell aside leaves 9 of 129, **7.0 in a hundred
with 3.7 to 12.7**. Both sit above the ceiling's 5 in a hundred, and the wider one excludes it.

**Depth does not help.** The ceiling is a fixed share of a reading's own depth, so it grows at 5 in
a hundred while this condition loses 7 to 11, and the expected losses exceed it at every depth. A
control reading passes 55% of the time at depth 5 and 1.6% at depth 120 on the wider rate, 70% and
26% on the narrower. A rate row is three control readings and three framed ones, so it draws clean
about one attempt in seven; a payload review row is nine and nine, which is one attempt in 280 at
the wider rate and one in 36 at the narrower, at 99 requests and about 25 minutes of card time an
attempt.

**The two failures are different kinds of loss.** At the corpus frame at the engine's budget the
mail control reading lost all five draws and drew none, so the row has no reading there at all and
the ceiling is not what refuses it. At the doubled frame at the shipped budget the dialog framed
reading lost one draw and drew four, and `rate` already printed
`framed 1/4 (mentioned 3/4), 1 void of 5`, so the ceiling of zero was the only thing between that
row and its six readings.

Three answers were available, and each re-reads every five-per-condition row already published.
Keeping the ceiling means reading the alt's rows as hand counts, where a review row prints eighteen
readings and a hand count of one is the whole row. Giving a reading the rule the matrix rows have,
counting a lost draw out of its denominator and failing only when lost draws outnumber drawn ones,
publishes the doubled frame at the shipped budget and still fails the corpus frame at the engine's
budget; its cost is that a five-draw reading may lose two and report a rate over three draws, which
is forty points of rate. Taking that rule per condition of the row rather than per reading publishes
both rows, and it is the variant the ceiling's own argument refused, since five of the six lost
draws fell in one condition of one cell.

A per-candidate ceiling set from each candidate's own loss rate is the fourth option and is refused
in writing: it holds a candidate that loses more to less, and two candidates' rows stop being read
against one rule. A cap and a per-draw retry stay refused for the reasons already recorded.

**What closed it.** `_VOID_SHARE` is one draw in five rather than one in twenty, so a five-draw
reading may lose one and a reading of 120 may lose twenty-four, and what a reading's lost draws
leave open is twenty points of rate at every depth. No published reading is withdrawn, since the new
ceiling is at or above the old one everywhere and no five-per-condition row on the page has a lost
draw.

## History

- 2026-09-12: opened by the run that drew the alt's six frame and budget rows, whose
  [ADR-0041 decision 4](../../adr/ADR-0041-injection-image-variant.md) publishes the four rows that
  passed, the two the ceiling failed, the per-condition loss rates and the depth table. Changing the
  ceiling is a decision about the instrument rather than a line of code, and widening an assertion
  at the end of a run to make a row pass is the one move that cannot be taken, so that run recorded
  its two rows as hand counts and left the rule alone. Written down then: neither failed row is
  redrawn at greater depth under any answer, and the mail control cell at the corpus frame at the
  engine's budget is not redrawn at all while it stands at six lost draws of six, since a seventh
  draw is a seventh loss in expectation.
- 2026-09-13: decided, as the second answer, checked against the price this entry claimed for it.
  The rule, the depths and the loss rates all recompute as written; the majority rule's cost is
  forty points at depth five rather than the twenty stated here. The doubled frame at the shipped
  budget publishes on a redraw and the dead mail cell still fails, which is what was written down.
  What the change costs a reader is a wider check by hand under a deep row's zero, which
  [ADR-0041 decision 14](../../adr/ADR-0041-injection-image-variant.md) records.
