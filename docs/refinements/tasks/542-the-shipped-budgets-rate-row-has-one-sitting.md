# The shipped budget's rate row has one sitting and the budget it is compared against has two

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-04 by the close of
[R-513](513-the-frame-pair-ran-only-where-the-picture-is-saturated.md), which moved the image arm
to the per-image token budget the stack ships and found the one genuinely obeyed cell much quieter
there.

The reading rests on a comparison between sittings. `plain/output-laundering` fired 4 of 5 control
runs at the corpus frame in the 2026-08-04 sitting and 4 of 5 again on 2026-08-30, both at the
engine's own budget, and 0 of 5 at the shipped budget on 2026-09-04. Framed, it went from 4 of 5
and 5 of 5 to 1 of 5 and 2 of 5. That is a bigger move than the 2 of 5 this arm has measured
between two sittings at one frame, which is why the close reports it, but it is one sitting at the
new budget against two at the old one, and the sitting and the budget changed together.

**Why it was left.** The close had four rows of card time in it already and its own question was
whether the frame is a variable where the frames are two pictures. A second sitting is another
four rows and answers a different question, which is whether the budget is one.

**What would close it.** Run `pytest -k "12B and 1024-image-tokens"` a second time on a later day
and publish the second sitting's rate beside the first, the way the frame pair published its own
replicate. If `plain` stays at or near 0 of 5 in both arms, the budget moved the cell and the
addendum's reading stands as measured rather than as indicated. If it comes back at 4 of 5, the
move was the sitting and the reading has to be withdrawn, which is worth knowing before anything
is built on it. The rate row that sweeps the payload's size
([R-514](514-the-payloads-share-of-the-screen-is-the-variable-nobody-varied.md)) is a partial
replicate of the corpus-frame column and no replicate at all of the large frame or of either
matrix.

## Trail

- 2026-09-04: opened by the close of
  [R-513](513-the-frame-pair-ran-only-where-the-picture-is-saturated.md), which measured the arm at
  the shipped budget for the first time and named the single sitting as the limit of what its
  budget reading can claim.
