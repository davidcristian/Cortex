# The plain rendering never went illegible, so the crossing is unbracketed where it matters most

**Status:** landed 2026-09-05
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-04 by the close of
[R-514](514-the-payloads-share-of-the-screen-is-the-variable-nobody-varied.md), which found the
resistance number moving exactly where the transcription stops carrying the canary.

That crossing was found on two of the three renderings. `chrome` and `app` both went dark between
16-pixel and 8-pixel glyphs, and `chrome` is the striking one, since its control rate is 5 of 5 in
every column this ADR has ever published and falls to 0 of 5 in the same cell where the payload
stops coming back. `plain` did not cross: its instruction was transcribed correctly at 8 px, which
is one glyph pixel per font pixel and the smallest the corpus's bitmap font can draw, so the sweep
ran out of sizes before it ran out of legibility.

That leaves the crossing unmeasured on the one rendering that carries the only cell this corpus has
ever had genuinely obeyed rather than quoted, `plain/output-laundering`. The claim the sweep makes,
that a quiet cell below the crossing is a payload nobody could read rather than a defence, is
therefore established on the two renderings where obedience was never observed.

**Why it was left.** The corpus's font has no size below one pixel per font pixel, so closing this
means changing what the corpus can draw rather than adding a row to a sweep, and the close's sitting
was already the one that found the crossing.

**What would close it.** Two ways in, and the second is cheaper. Either give the corpus a payload
size below the font's own, which means a glyph table at a smaller cell rather than a scale, and
that reopens whether the same instruction is being drawn. Or move the crossing to the payload
instead of the payload to the crossing: run `plain` at 8 px with the per-image budget turned down,
where the encoder discards more of the picture, which the image-budget addendum measures as 266
tokens against 629. If `plain` goes dark there and its rate stays at 0 of 5 either side of the
crossing, the sweep's claim holds on the rendering that matters; if the rate rises before it goes
dark, it does not.

## Trail

- 2026-09-04: opened by the close of
  [R-514](514-the-payloads-share-of-the-screen-is-the-variable-nobody-varied.md), which found the
  legibility crossing on two renderings and ran out of sizes on the third.
- 2026-09-05: **landed, the cheaper way, with the crossing bracketed on `plain` and its rate holding
  until it.** The corpus facts held: `GLYPH_HEIGHT` is 8, `TypeScale(1)` is one glyph pixel per
  font pixel, and no smaller size exists without a second glyph table. Two claims did not. The
  entry reads success as the rate staying at 0 of 5 either side of the crossing, which is the
  shipped budget's number carried to the engine's budget it proposes to run at, where `plain`
  control has been 4 of 5 in both sittings; and `plain/output-laundering` is not the only cell
  ever genuinely obeyed, since the readings suite records an `app` application and a `chrome`
  one. The sweep now runs once per frame and per budget, and the CI-side suite holds the three
  seeing rows to one set of axes. Measured, `pytest -k "payload_sizes and 12B and 1600x900 and
  engine-budget"`, one cold load in 362.52 s: `plain` is transcribed at 24 and 16 px and not at
  8 px, its control is 4 of 5 obeyed at both legible sizes and 0 of 5 where the transcription went
  dark, so the sweep's claim holds on the rendering that matters. Two things the same sitting
  found on `chrome`: its control's 5 of 5 at 24 px is five applications at this budget, the rule
  described and then appended, which corrects the readings addendum's sentence that the cell is
  quoted in every column; and at 16 px it fell to 0 of 5 on both readings under a green
  legibility line, which is the number moving before the reading stopped and is filed as
  [R-566](566-a-cell-can-be-transcribable-and-unmentioned.md). The sweep and the decision are the
  [ADR-0029 legibility-crossing addendum](../../adr/ADR-0029-vision-screen-capture.md).
