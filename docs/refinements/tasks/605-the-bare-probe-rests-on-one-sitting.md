# The unstyled probe carries half the square's answer and has one sitting behind it

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-09

Opened 2026-09-07 by the close of
[R-579](579-the-dialog-summarises-past-its-payload-one-size-early.md), which drew the four corners
of the square once each and the dialog pair twice.

Half of that close rests on `bare`, the unstyled screen whose whole content is the payload. It put
the rule verbatim into all 10 of its summaries at 16 px and 8 of 10 at 24 px, which is what refuses
the candidate that naming a screen whose content is the payload is already a complete summary of
it, and it applied the rule in none of the 10 control draws it has at those two sizes where `plain`
applied it in 8 of 10, which is what says a body above the payload turns a described rule into an
applied one. Both readings come from one row in one load, and the dialog pair drawn twice the same
night disagreed with itself about a control arm, 4 of 5 in one sitting and 1 of 20 in the next.

**Why it was left.** The sitting had two loads in it and spent the second separating the dialog
pair, which was the marginal contrast of the two at five draws an arm. `bare` was 10 of 10 against
`chrome`'s 2 of 10 in the same load, which is one chance in fourteen hundred of being one rate, so
it was the contrast that did not look like it needed a second load. What the dialog pair then
showed is that a cell can settle on one answer per load, which is a reason to doubt any cell with
one load behind it however wide its margin.

**What would close it.** Draw `bare` and `plain` at 16 px and at 24 px, twenty per arm, in one
load, the way the dialog pair was drawn. If `bare` comes back near 20 of 20 mentioned and 0 of 20
applied while `plain` comes back near 16 of 20 applied, both halves of the square's answer stand on
two sittings and the addendum can say so. If either moves, the reading that moves is the one the
close overstated, and the entry says which.

## Trail

- 2026-09-07: opened by the close of
  [R-579](579-the-dialog-summarises-past-its-payload-one-size-early.md), whose
  [ADR-0029 body-and-chrome addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes the
  one sitting this probe has.
- 2026-09-09: claims held to the tree. `bare` still has the one sitting, since nothing has drawn it
  again and it appears only in the square's payload sweep. One count was wrong: the control arm the
  applied reading is read over was written as 20 draws, and the sweep drew `bare` five control
  draws at each of the two legible sizes, which is the 10 the addendum states it as.
