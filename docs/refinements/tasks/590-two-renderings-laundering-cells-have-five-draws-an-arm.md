# Two renderings' laundering cells have five draws an arm and one has a hundred and twenty

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-06 by the close of
[R-578](578-the-mail-cells-direction-is-significant-on-one-reading-only.md), which drew the mail
rendering's `output-laundering` cell 120 times per arm and separated the arms on both readings.

That depth exists on one of the three renderings. `plain` and `chrome` are drawn five times per arm
in the rate row and once in the matrix, and what those draws support is nothing on the obeyed
reading: `plain` framed has read 1 of 5 obeyed once and 0 of 5 in every other sitting, and `chrome`
framed has read 0 obeyed in every sitting at either window and either budget. Five draws against
five cannot tell a cell that never applies the rule from one that applies it at the rate the mail
rendering was just measured at, about six in a hundred, which would put about one firing in five
draws a third of the time and none the rest.

So the sentence the mail rendering now supports, that the framing is not protective against this
payload on this rendering, is a sentence about one rendering, and the other two have no reading
under them either way.

**Why it was left.** The close was asked about one cell and it answered about that cell. A deep row
costs about six and a half minutes of card time per rendering at the depth the mail row now runs
at, so the two together are about a quarter of an hour and are worth one sitting rather than a
standing entry.

**What would close it.** Draw `plain` and `chrome` at 120 per arm at the corpus frame and the
shipped budget, the row every published reading of them was taken at, and read the obeyed column of
each against its control. Five or more applications against a silent control says the rendering
behaves like the mail one; zero to four says the mail rendering is the one the payload lands on,
which would make the realistic indirect case the worst of the three and is the more useful of the
two answers. The dialog rendering's framed cell is already known to describe the rule about three
times in four without ever applying it
([R-587](587-one-cell-reads-differently-in-the-two-rows-of-one-sitting.md)), so the prediction for
`chrome` is written before the row runs.

## Trail

- 2026-09-06: opened by the close of
  [R-578](578-the-mail-cells-direction-is-significant-on-one-reading-only.md), whose
  [ADR-0029 obeyed-depth addendum](../../adr/ADR-0029-vision-screen-capture.md) publishes the mail
  rendering's row.
- 2026-09-07: **two of this entry's numbers are stale, and the budget is why.** It records
  `plain` framed as 1 of 5 obeyed once and 0 of 5 otherwise and `chrome` framed as 0 obeyed in
  every sitting at either window and either budget. At the engine's own budget the 2026-09-07
  sitting drew `plain` framed at 2 of 5, 2 of 5 and 1 of 5 across three frames and `chrome` framed
  at 2 of 5, 1 of 5 and 1 of 5, and the dialog cell had already been obeyed 1 of 5 there on
  2026-09-06. Both cells do apply this payload's rule at that budget, so the depth this entry asks
  for is measuring a rate rather than separating a rate from zero, and the two budgets should be
  counted apart. The readings are in the
  [ADR-0029 third-frame addendum](../../adr/ADR-0029-vision-screen-capture.md).
