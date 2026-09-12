# The void ceiling is a share the cortex alt's control arm is above

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-12

Opened 2026-09-12 by the sitting that drew the cortex alt's frame and budget rows, two of which the
ceiling failed ([R-607](607-eighteen-of-the-cortex-alts-pixel-rows-are-undrawn.md), the
[ADR-0029 frame-and-budget addendum](../../adr/ADR-0029-vision-screen-capture.md)).

`assert_drawn` holds each reading, one arm of one cell, to `runs // _VOID_SHARE` void draws, and
`_VOID_SHARE` is 20. A rate row and a payload sweep draw `_RATE_RUNS`, which is 5, so their readings
have a ceiling of zero and one empty or capped reply fails the whole row. One in twenty was set from
the pick: its two deep rows at the engine's own budget lost 4 draws in 480, 0.83 in a hundred, and
the share is twice the worst reading that measured
([R-603](603-the-engine-budgets-deep-row-voids-on-draws-that-think-to-the-cap.md), the
[ADR-0029 void-ceiling addendum](../../adr/ADR-0029-vision-screen-capture.md)).

The alt is above that share. Over the six rows drawn on 2026-09-12, 270 scored vision turns, its
control arm returned 15 empty replies in 135 draws, **11.1 in a hundred with 6.9 to 17.5 under it**,
against 1 in 135 in the framed arm. Six of the fifteen are one mail cell that answered nothing in six
draws of six; setting that cell aside leaves 9 of 129, **7.0 in a hundred with 3.7 to 12.7**. Both
readings sit above the ceiling's 5 in a hundred, and the wider one excludes it.

**Depth is not the lever.** The ceiling is a fixed share of a reading's own depth, so it grows at 5
in a hundred while this arm voids at 7 to 11, and the expected voids exceed it at every depth. A
control reading passes 55% of the time at depth 5 and 1.6% at depth 120 on the wider rate, 70% and
26% on the narrower. A rate row is three control readings and three framed ones, so it draws clean
about one attempt in seven; a payload sweep row is nine and nine, which is one attempt in 280 at the
wider rate and one in 36 at the narrower, at 99 requests and about 25 minutes of card time an
attempt. So the four sweep rows on R-607's list are not drawable for this candidate under this rule,
and its two failed rate rows are not worth redrawing at any depth.

**The two failures are different kinds of loss, and that is what picks the answer.** At the corpus
frame at the engine's budget the mail control reading lost all five draws and drew none, so the row
has no reading there at all and the ceiling is not what is refusing it. At the doubled frame at the
shipped budget the dialog framed reading lost one draw and drew four, and `rate` already printed
`framed 1/4 (mentioned 3/4), 1 void of 5`, so the ceiling of zero is the only thing between that row
and its six readings.

**Why it was left.** Changing the ceiling is a decision about the instrument, not a line of code, and
the argument it would overturn is published: a reading of four instead of five widens what the row
leaves open by twenty points of rate, and every row on the page was published under the tighter rule.
Widening an assertion at the end of a sitting to make a row pass is the one move that cannot be taken
here, so the sitting recorded its two rows as hand tallies and left the rule alone.

**What would close it.** Pick one of three and record it, which re-reads every five-per-arm row
already published.

- **Keep the ceiling** and read the alt's five-per-arm rows as hand tallies in an addendum, which is
  what 2026-09-12 did. The price is that a sweep row prints eighteen readings, so a hand tally of one
  is the whole row, and the counts a reader compares are not the ones a harness produced.
- **Give a reading the rule the matrix rows already have**: count a void draw out of its denominator,
  which `rate` already prints, and fail a reading only when its void draws outnumber its drawn ones,
  the way `assert_measured` holds a matrix arm. On 2026-09-12 that publishes the doubled frame at the
  shipped budget, 1 void against 4 drawn, and still fails the corpus frame at the engine's budget, 5
  void against none drawn. The cost is the twenty points of rate the ceiling addendum priced.
- **Take that rule per arm of the row rather than per reading**, which publishes both rows, 5 void
  against 25 drawn and 1 against 29. This is the variant the ceiling's own argument refused, in the
  words "a share taken over 720 could fall entirely in one arm of one cell", and on 2026-09-12 that
  is exactly where five of the six void draws fell. Taking it now means answering that argument
  rather than passing it.

A cap and a per-draw retry stay refused for the reasons the void-ceiling addendum gives, and neither
is on this list.

A per-candidate ceiling set from each candidate's own void rate is the fourth move and the one to
refuse in writing: it holds a candidate that voids more to less, and two candidates' rows stop being
read against one rule.

**Pre-registered on 2026-09-12, before any redraw.** Neither failed row is redrawn at greater depth
under any answer, for the arithmetic above. If the second answer is taken, neither row needs a redraw
at all: the log holds all twelve readings and the only one it cannot publish is the dead mail cell. If
the ceiling is kept, the two rows are redrawn at depth five unchanged, and the price is on the page: a
rate row is 33 requests, about eight minutes at the 15 s a request that sitting measured, drawing
clean about one attempt in seven, so publishing one of the two costs about an hour of card time in
expectation and both about two and a half. The mail control cell at the corpus frame at the engine's
budget is not redrawn under any answer while it stands at six void draws of six, since a seventh draw
is a seventh void in expectation.

## Trail

- 2026-09-12: opened by the sitting that drew the alt's six frame and budget rows, whose
  [ADR-0029 frame-and-budget addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes the four
  rows that landed, the two the ceiling failed, the per-arm void rates and the depth table.
