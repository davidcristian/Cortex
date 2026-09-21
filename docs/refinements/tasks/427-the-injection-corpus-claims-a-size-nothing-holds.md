# The injection corpus calls its size the body's own output and nothing checks that

**Status:** done 2026-08-25
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)

`brain/packages/inference/tests/rendered_screens.py` renders the screens the image-variant
injection defence is measured against. It declares `WIDTH = 1600` and `HEIGHT = 900`, and its
module docstring says the size is the body's own output and that the corpus declares a 2560x1440
source so the tool's stand-in text says `downscaled from` exactly as a real capture would. The
whole argument for those numbers is that they are what a real capture looks like to the model.

Neither half of that claim is checked. The brain has asked the body for a 2048 px edge since the
legibility pair was added, so what a shipped deployment captures is 2048x1152 and not 1600x900; the
corpus is sized on the body's own default, which is what a request naming no edge gets and not what
this stack sends. And nothing ties the fixture's `WIDTH` to either number, so both can move while
the docstring goes on saying otherwise.

Three options. Track the shipped request (2048x1152), which makes the corpus match what the cortex
really sees and needs the registry to tie `WIDTH` to `DEFAULT_CAPTURE_MAX_EDGE`. Track the body's
own default and keep the docstring's sentence, which needs a registry row. Or declare the size the
fixture's own choice, drop the claim, and say instead why that resolution is the one the defence is
measured at. The third is cheapest and is only accurate if the size does not change the result,
which is one live run of the image variant at both sizes to find out
([the harness](258-image-arm-injection-harness.md) is where that would go).

## History

- 2026-08-25: opened by the close of
  [R-399](399-the-body-edge-is-two-sites-and-no-prose.md), which read this file's `1600`s as a
  fixture's own choice and found the docstring claiming they were not.
- 2026-08-25: closed as the third option, with no registry row. Both numbers are what this entry
  said they are, and the docstring's claim is wrong before either can move: a capture naming no
  edge comes back at the body's own default and the brain names an edge of its own, so no capture
  the shipped stack takes is the corpus's size. Tracking either number was rejected. Registering
  the sentence would fix it against a literal beside it that is free to change, and tying the frame
  to the shipped request would re-render every cell and break comparison with the published
  resistance matrix without anything reporting it. What replaces the claim is the argument that was
  already true and unwritten: the matrix was measured in this frame, and a payload at a fixed glyph
  size fills more of a small frame, so this is the legible end and the end a defence measurement
  should err on, which the image variant's own Chromium control already measured.
  `test_image_variant.py` had a second copy of the old claim that this entry did not mention, and it
  is corrected too. Whether the size changes the result is unmeasured and is now
  [R-432](432-the-image-arm-has-never-run-at-two-sizes.md). The decision is
  [ADR-0041 decision 4](../../adr/ADR-0041-injection-image-variant.md).
