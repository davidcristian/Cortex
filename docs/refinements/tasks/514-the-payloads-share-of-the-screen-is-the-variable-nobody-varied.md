# The corpus has only ever drawn a payload that fills the screen it is drawn on

**Status:** done 2026-09-04
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

The frame pair magnifies every coordinate and every glyph pixel by the same integer, so a payload
occupies exactly the same share of the picture at both frames and the size is the only thing that
differs. That is what makes the two rows a comparison rather than two experiments. It also means the
corpus has only been drawn one way: the instruction is set in glyphs 24 pixels tall against a
900-pixel-tall screen, a payload a reader could not miss.

A real indirect attack does not get to pick that ratio. An injected paragraph in the tail of a mail
message on a 4K desktop is body text, and the same record that measured the legibility numbers found
that ordinary interface text does not survive the capture downscale at the shipped budget while
comfortable prose does. So the payload sits at the legible end of a range whose other end is
measured to be unreadable, and nothing has measured where in that range the resistance number stops
being about the framing and starts being about legibility.

## History

- 2026-08-30: opened by the close of
  [R-432](432-the-image-variant-is-unmeasured-at-other-picture-sizes.md), which held the payload's share of the
  picture constant on purpose and named that as the variable it did not vary.
- 2026-09-04: closed, with the number flat across the legible range and moving where the reading
  stops. Every particular about the corpus held: all three renderings drew their payload at one
  glyph scale, and no caller could ask for another. What the entry placed wrongly is the far end of
  the range, which it took from legibility numbers measured on 4K desktops downscaled to a capture
  edge; on this corpus's own screens at the shipped budget the `plain` instruction is still
  transcribed at 8-pixel glyphs, the smallest the font draws. The corpus now takes a `TypeScale`
  that multiplies the payload's glyphs alone, with the wrap width growing inversely so the paragraph
  keeps its column, and `test_image_variant.py` requires the first row a size changes to be the row
  its rendering declares. The `output-laundering` rate ran at 24, 16 and 8 px on all three
  renderings inside one server, with a transcription before each cell and legibility recorded rather
  than asserted. Between 24 and 16 px nothing moved outside this measurement's own instability. At 8
  px `chrome` control fell from 5 of 5, its value in every column ever published, to 0 of 5, and the
  transcription in the same cell came back without the canary: resistance does not rise before the
  payload stops arriving, it rises when it does. What is left is that the share and the pixels per
  glyph are one variable at one frame
  ([R-544](544-share-and-glyph-pixels-are-one-variable-at-one-frame.md)) and that `plain` never
  crossed ([R-545](545-the-plain-renderings-legibility-floor-is-not-bracketed.md)). The measurement
  and the decision are [ADR-0041](../../adr/ADR-0041-injection-image-variant.md).
