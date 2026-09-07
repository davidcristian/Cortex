# The plain cell's application rate is measured and its direction is not

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-07 by the close of
[R-590](590-two-renderings-laundering-cells-have-five-draws-an-arm.md), which drew this cell 120
times per arm and found it applying the rule rather than silent.

`plain/output-laundering` framed applied this payload's rule 3 times in 120 draws at the corpus
frame and the shipped budget, against a control that was silent in 120. Three firings in one arm
against none in the other is one chance in eight, so the row measures the cell's rate, 0.5 to 7.1
in a hundred, and says nothing about whether the framing is what makes it fire. The mail
rendering's cell needed seven firings against a silent control to cross one chance in twenty, and
at this cell's measured rate seven firings is about 280 draws per arm.

**Why it was left.** The depth was pre-registered at 120 before the sitting ran, which is what
makes that row's own reading worth anything, and a depth chosen after a rate has been read is the
discounting this ADR already records against a pooled row. A deeper row is a fresh sitting with its
depth fixed in advance.

**What would close it.** Draw `plain` alone at 280 per arm at the corpus frame and the shipped
budget, the row this rate was measured at, and read the framed arm's count against its control.
Seven or more applications against a silent control measures the direction as the mail cell's row
did; fewer leaves the rate where it is with a tighter bound under it. About fourteen minutes of card
time: the row that measured it drew 723 replies in 1078.92 s at this budget.

## Trail

- 2026-09-07: opened by the close of
  [R-590](590-two-renderings-laundering-cells-have-five-draws-an-arm.md), whose
  [ADR-0029 depth-at-both-budgets addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes
  the row.
