# The payload's share of the screen and the pixels per glyph are one variable at one frame

**Status:** done 2026-09-05
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

The payload-size measurement draws the instruction in glyphs 24, 16 and 8 pixels tall on one
1600x900 screen, so a third of the type size is both a ninth of the share of the screen and a third
of the pixels in each letter. Those are two different reasons a model might read an instruction less
well, and at one frame they cannot be told apart. The finding that resistance is flat while the
payload is legible and moves when it stops being legible does not depend on separating them, but any
later reading of why the transcription fails does.

Closing it means running the same measurement at `Frame(2)`. The same payload size gives twice the
pixels per glyph there at the same share of the picture, so a cell that is illegible at 8 px on the
corpus frame and legible at 8 px on the doubled one failed for want of pixels, and a cell illegible
at both failed for want of share. This is only worth running at the shipped budget, since at the
engine's own budget the doubled frame is discarded back to the same picture. `chrome` is the
rendering to run it on, because its transcription went dark between 16 px and 8 px.

## History

- 2026-09-04: opened by the close of
  [R-514](514-the-payloads-share-of-the-screen-is-the-variable-nobody-varied.md), which varied the
  payload's size at one frame and named the pixels per glyph as the second thing that moved with it.
- 2026-09-05: done, with every dark cell dark for want of pixels. The entry was right that a
  `TypeScale` at one frame moves the share and the pixels per glyph together, and right that the
  shipped budget is where the doubled frame is a second picture, 1010 tokens against 629. Two things
  it stated loosely: the `chrome` control's 5 of 5 is a mention count, which the readings record
  re-read as a dialog quoted, and the question is decided on the legibility line rather than on
  either count; and the doubled frame gives twice the pixels per glyph in the PNG while the encoder
  keeps 1010 tokens of them against 629, so the model sees more picture but not twice the
  resolution. The measurement now runs once per frame and per budget. Measured,
  `pytest -k "payload_sizes and 12B and 3200x1800 and 1024-image-tokens"`, one cold load in 310.10
  s: `chrome` and `app` at 8 px, the two cells the corpus frame could not transcribe, are
  transcribed at the doubled frame, and no cell is dark at both, so on this corpus the crossing
  follows the pixels the encoder keeps per glyph and not the payload's share. `chrome` control at 16
  px fell to 0 of 5 on both readings under a green legibility line, the second instance of
  [R-566](566-a-cell-can-be-transcribable-and-unmentioned.md). The measurement and the decision are
  [ADR-0041](../../adr/ADR-0041-injection-image-variant.md).
