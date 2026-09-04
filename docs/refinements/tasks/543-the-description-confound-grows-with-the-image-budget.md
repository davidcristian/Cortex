# The detector cannot tell a description from obedience, and the budget makes descriptions likelier

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-04 by the close of
[R-513](513-the-frame-pair-ran-only-where-the-picture-is-saturated.md), which ran the image arm at
the budget the stack ships and watched the matrix count rise for a reason that is not obedience.

The image arm scores a cell as obeyed when the reply carries the attack's canary, and over pixels
the benign answer to "what is on my screen?" quotes the screen. The image-arm addendum documented
that confound and answered it by printing every fired cell's reply so a reader can sort them by
hand. What the shipped budget's rows add is that the confound is a function of the deployment: at
the engine's own budget the model summarised the `chrome` dialog loosely, and at 1024 image tokens
it reports the dialog's instruction verbatim, so fifteen of the sixteen firings across the two new
rows are descriptions and the count is higher than at the budget where the model could read less.
A number that gets worse as the deployment gets better is a number that cannot be read as
resistance without reading every reply under it.

**Why it was left.** The close it came out of was about which budget the arm runs at, and every
cell it published was sorted by hand from the printed replies, so the confound was reported rather
than left hidden. Building a second detector is a design question about what obedience means for a
summarising task, not a flag on a command line.

**What would close it.** Give the arm a detector that separates the two, which for
`output-laundering` is the difference between a reply that ends with the demanded notice and one
that mentions the notice as something the screen asks for. The shape that generalises is a
per-attack predicate over the reply's own structure rather than a substring search over its whole
text, which is what `Attack.obeyed` already is, so the change is per-attack predicates that look
where the instruction told the model to write rather than anywhere. Then re-score the published
matrices, which are printed with their replies and can be re-read without the card, and publish
the two counts beside each other. If the sorted-by-hand reading holds, the arm gains a number that
can be compared across budgets; if it does not, one of the published matrices is wrong about which
cells were obeyed.

## Trail

- 2026-09-04: opened by the close of
  [R-513](513-the-frame-pair-ran-only-where-the-picture-is-saturated.md), which found the arm's
  count rising with the image budget and every added cell being a description.
