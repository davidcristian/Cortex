# The corpus has only ever drawn a payload that fills the screen it is drawn on

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-30 by the close of
[R-432](432-the-image-arm-has-never-run-at-two-sizes.md), which varied the picture's size with the
payload's share of it held constant, deliberately and for a stated reason.

The frame pair that close published magnifies every coordinate and every glyph pixel by the same
integer, so a payload occupies exactly the same share of the picture at both frames and the size
is the only thing that differs. That is what makes the two rows a comparison rather than two
experiments, and it is also what lets the close rule a size effect out: the two arms of one frame
share a byte-identical picture, so anything the size did would move them together. It also means
the corpus has still only been drawn one way: the instruction is set in glyphs 24 pixels tall
against a 900-pixel-tall screen, which is a payload a reader could not miss.

A real indirect attack does not get to pick that ratio. An injected paragraph in the tail of a
mail message on a 4K desktop is body text, and the same addendum that measured this ADR's
legibility numbers found that ordinary interface text does not survive the capture downscale at
the shipped budget while comfortable prose does. So the arm's payload sits at the legible end of a
range whose other end is measured to be unreadable, and nothing has measured where in that range
the resistance number stops being about the framing and starts being about the eyesight.

**Why it was left.** The close it came out of had one question in front of it, whether the
measured resistance moves with the picture's size, and answering it required holding the share
constant. Varying the share in the same sitting would have moved two things at once and neither
answer would have survived. It is also a different kind of work: a share sweep is several rows
rather than a pair, and it wants a rendering whose payload is set at a chosen fraction of the
screen rather than at the one size the three renderings share.

**What would close it.** Give the corpus a payload scale that is independent of its frame, render
one rendering's `output-laundering` cell at several shares of the screen, and run the framed and
control arms at each on the shipped cortex. The legibility line is the gate that makes the sweep
readable: the interesting number is not where resistance goes up but whether it goes up *before*
the transcription stops carrying the canary, since a payload the model cannot read is a defence
nobody built. `brain/packages/inference/tests/rendered_screens.py` already separates layout units
from delivered pixels, so the scale that needs adding is a second multiplier on the glyphs alone.

## Trail

- 2026-08-30: opened by the close of
  [R-432](432-the-image-arm-has-never-run-at-two-sizes.md), which held the payload's share of the
  picture constant on purpose and named that as the variable it did not vary.
