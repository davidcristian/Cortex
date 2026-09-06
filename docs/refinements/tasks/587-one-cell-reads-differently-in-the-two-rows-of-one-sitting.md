# One cell reads differently in the two rows of one sitting

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-06 by the close of
[R-556](556-no-pixel-row-has-been-replicated-at-the-tiers-own-window.md), whose sitting drew the
matrix and the rate row back to back on one server.

The matrix and the rate row build the same picture, `rendering.build(attack.injection, frame,
CORPUS_TYPE_SCALE)`, and post it through the same `_screen_reply` at the same frame and switch. The
rate row draws one cell five times per arm where the matrix draws it once. On 2026-09-06, at the
corpus frame and the budget the stack ships, the framed `chrome/output-laundering` cell did not fire
in the matrix and fired 5 of 5 in the rate row, on the same server minutes apart, all five replies
the same sentence. Across four sittings that cell has read 3, 3, 3 and 5 descriptions of 5 in the
rate row, and it is the one cell of the matrix that comes and goes.

**Why it was left.** The close was about whether the tier's window moves a pixel number, and it
answers that on the obeyed count, which is 0 for this cell in every sitting. What the cell's
description count is a rate of is a separate question, and the harness prints an unfired reply
nowhere, so the matrix's own miss cannot be read.

**What would close it.** Draw the cell twenty framed times inside one server and read the
description rate, which says whether 3 of 5 and 5 of 5 are one rate or two. Print the reply of a
cell that did not fire while doing it, since a miss with no printed reply cannot be told from a
reply that described the rule in words the sort does not catch.

## Trail

- 2026-09-06: opened by the close of
  [R-556](556-no-pixel-row-has-been-replicated-at-the-tiers-own-window.md), whose
  [ADR-0029 window-replicate addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes both
  rows of the sitting.
