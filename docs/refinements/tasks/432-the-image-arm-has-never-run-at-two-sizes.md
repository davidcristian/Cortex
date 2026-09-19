# Nobody has measured whether the image variant's result depends on the picture's size

**Status:** done 2026-08-30
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

The image variant of the injection harness renders its screens at one frame size, and that size is
argued for rather than borrowed: the published resistance matrix was measured in it, and a payload
drawn at a fixed glyph size fills more of a small frame than of a large one, so it is the legible
end of what a screen can arrive at. Both halves of that argument are about comparison and about
erring on the attacker's side, not about the number. Neither establishes whether the measured
resistance moves with the picture's size at all.

The size plausibly could matter. The encoder resizes whatever it is handed onto its own grid, so a
payload occupying a smaller fraction of a larger frame arrives with fewer pixels per glyph, and the
whole premise is that the model reads the instruction. If resistance is the same across the two
edges a deployment can send, the corpus's frame is a free choice. If it is not, the published
number is a number about one resolution and the matrix needs a second column.

The work is a live GPU run of a multimodal model over the whole corpus in both variants, twice:
render the corpus at a second frame, the one a shipped deployment's request produces, run
`brain/packages/inference/tests/test_injection_defense_live.py` with `-k "pixels and 12B"` at both
on the shipped cortex with its projector, and publish both matrices against each other.

## History

- 2026-08-25: opened by the close of
  [R-427](427-the-injection-corpus-claims-a-size-nothing-holds.md), which argued the corpus's frame
  from comparison and from the attacker's benefit and found no evidence either way about whether
  the frame changes the result.
- 2026-08-30: closed, with the frame a free choice over the range measured and the entry's own
  experiment rejected. Every particular of the entry held: one frame was the only frame the corpus
  could build, and the published matrix was measured in it. The experiment it proposed was not run,
  because a canvas that grows while the glyphs stay put varies the payload's share of the picture
  as well as the picture's size, and two matrices differing in two variables are two experiments.
  The corpus now takes a `Frame` that multiplies the canvas, every coordinate and every glyph pixel
  by one integer, so the payload holds its share exactly and size is the only variable; the variant
  ran at the corpus frame and at twice it on the shipped cortex, uncapped, and the rate of the one
  genuinely obeyed attack was measured at both. The matrices differ by three cells and all three
  are cells already measured to happen on about half their runs, and the rate is what settles how
  to read that: the same cell moved by 2 of 5 between two measurement sessions at one frame and by
  2 of 5 between two frames in one session, so the result is an upper bound on any size effect
  rather than its absence. What is excluded is anything that would have shown, since the two
  variants moved apart rather than together and the picture is byte-identical between them. What
  the pair cannot settle is that it ran at the one image budget where a larger picture is not a
  larger picture to the model, which is
  [R-513](513-the-frame-pair-ran-only-where-the-picture-is-saturated.md), and it deliberately held
  the payload's share of the screen constant, which is
  [R-514](514-the-payloads-share-of-the-screen-is-the-variable-nobody-varied.md). The decision and
  both matrices are [ADR-0041 decision 4](../../adr/ADR-0041-injection-image-variant.md).
