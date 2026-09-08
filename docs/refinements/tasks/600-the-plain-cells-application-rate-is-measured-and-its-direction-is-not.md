# The plain cell's application rate is measured and its direction is not

**Status:** landed 2026-09-08
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
- 2026-09-08: **landed at the pre-registered depth, and the direction is measured on one of the
  two readings.** Re-derived first, and one sentence of this entry is wrong about its own
  arithmetic: it says the mail cell "needed seven firings against a silent control to cross one
  chance in twenty", and five firings against a silent control is one chance in thirty-two, which
  crosses it. Five is the count the
  [ADR-0029 obeyed-depth addendum](../../adr/ADR-0029-vision-screen-capture.md) pre-registered, and
  the mail cell's seven is one chance in a hundred and forty. The error costs nothing here, because
  the row drew four. `plain` alone at 280 per arm at the corpus frame and the shipped budget, in
  688.00 s with no empty or capped reply, applied the payload's rule **4 times in 280** against a
  control silent in 280, and mentioned the token **7 times in 280** against a control that
  mentioned it in none. Four applications against a silent control is one chance in sixteen, short
  of both this entry's seven and the five that crosses one chance in twenty, so the direction on
  the obeyed reading stands where the 120-draw row left it. What the depth bought is the tighter
  bound this entry asked for as its other branch: the rate is 1.43 in a hundred, 0.39 to 3.62, and
  four or fewer in 280 at the mail cell's 5.8 is one chance in four thousand. On the mention
  reading the same row does measure the direction, 7 of 280 against 0 of 280 being one chance in a
  hundred and thirty-three, so the framing is what puts this payload's token into a reply on this
  rendering; the 120-draw row carried that reading already at 6 of 120 against none, one chance in
  sixty-eight, and reported only the obeyed counts. The obeyed direction is opened as
  [612](612-the-plain-cells-obeyed-direction-is-unmeasured-at-280-draws-an-arm.md). The row is the
  [ADR-0029 two-pre-registered-rows addendum](../../adr/ADR-0029-vision-screen-capture.md).
