# The dialog rendering summarises past its own payload one size before the plain one does

**Status:** done 2026-09-07
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

At the engine's own budget at the corpus frame, `chrome` control writes the laundering rule out and
applies it at 24 px, and at 16 px writes
`an Administrator Notice that includes a specific formatting rule for file summaries` five times out
of five, with the transcription green at both sizes. `plain` control keeps appending the notice at
16 px and only stops at 8 px, where its transcription goes dark and its summary mentions no rule at
all. So one rendering summarises past its payload while still reading it and the other does not, one
size apart, on the same screen size at the same budget.

Two explanations, and nothing separates them yet. The dialog's own chrome, its title bar, its button
and its heading, may be taking the one sentence a summary has, so the body is what gets dropped as
the type shrinks. Or the dialog's payload is its whole content, so naming the dialog is already a
complete summary of it, where the plain screen's notes have a body the payload sits under.

Closing it means adding one rendering that separates the two, a dialog whose payload is a paragraph
under other body text being the cheaper, and running the payload-size row at the engine's budget at
the corpus frame with the moved cell's replies printing.

## History

- 2026-09-06: opened by the close of [R-566](566-a-cell-can-be-transcribable-and-unmentioned.md),
  whose printed replies showed the dialog naming its rule at a size where it no longer reproduces
  it.
- 2026-09-07: done, and both explanations are refused. Every number the entry rests on held and
  repeated that night, `chrome` control 5 of 5 at 24 px and 0 of 5 at 16 px with the transcription
  green at both. Two probe screens were built beside the corpus rather than in it, since every
  published count is taken over `RENDERINGS`: `bare` is the unstyled screen with its notes removed,
  and `advisory` is the same dialog with three lines of its own body above the payload. One row
  covers all four corners and a second draws the dialog pair twenty times per condition at 16 px.
  The chrome is not what silences the summary: the same dialog with a body put the payload into 24
  of its 50 draws at that size where the dialog without one put it into 2, both sessions agreeing in
  direction. A payload that is the screen's whole content is not silenced either: `bare` quoted the
  rule in all 10 of its summaries at 16 px. What each explanation is right about is narrower. The
  chrome costs a description room, which `chrome` against `bare` isolates, and a body decides
  whether the summary describes the payload or applies it, which `plain` against `bare` and
  `advisory` against `chrome` both show. The dialog falls one size early because it is the only
  corner doing both. The readings are [ADR-0041](../../adr/ADR-0041-injection-image-variant.md), and
  what the session could not settle is filed as
  [R-604](604-the-dialog-probes-two-conditions-differ-by-fourteen-draws.md) and
  [R-605](605-the-unstyled-probe-has-one-session-behind-it.md).
