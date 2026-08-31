# The injection corpus calls its size the body's own output and nothing holds it to one

**Status:** landed 2026-08-25
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-25 by the close of
[R-399](399-the-body-edge-is-two-sites-and-no-prose.md), which sorted seventy spellings of the
body's default edge and left this one deliberately unsorted.

`brain/packages/inference/tests/rendered_screens.py` renders the screens the image-arm injection
defence is measured against. It declares `WIDTH = 1600` and `HEIGHT = 900`, and its module
docstring says "The size is the body's own output, 1600x900, and the corpus declares a 2560x1440
source so the tool's stand-in text says `downscaled from` exactly as a real capture would". The
whole argument for those numbers is that they are what a real capture looks like to the model.

Two things are true of that claim now and neither is held anywhere. The brain has asked the body
for a **2048** px edge since the legibility pair landed, so what a shipped deployment actually
captures is 2048x1152 and not 1600x900; the corpus is sized on the body's own default, which is
what a request naming no edge gets and not what this stack sends. And nothing ties the fixture's
`WIDTH` to either number, so both can move while the docstring goes on saying otherwise.

**Why it was left.** The survey it came out of was about which prose states the body's default, and
this is the opposite question: whether a fixture that says it copies a live size should be held to
one, and if so to which of two. Registering the docstring alone would freeze the sentence against a
number the fixture beside it is free to leave, which is worse than not registering it. And the
underlying question is about the injection defence rather than about the gate: whether the measured
resistance depends on the picture's size at all, which nobody has measured.

**What would close it.** Decide what the corpus is sized on, and say it in one place. Three shapes
are worth weighing. Track the shipped ask (2048x1152), which makes the corpus match what the cortex
really sees and needs the registry to tie `WIDTH` to `DEFAULT_CAPTURE_MAX_EDGE`. Track the body's
own default and keep the docstring's sentence, which is what the file says today and needs a row
for the same reason the prose around that constant now has seventeen. Or declare the size the
fixture's own choice, drop the "body's own output" clause, and say instead why that resolution is
the one the defence is measured at. The third is cheapest and is only honest if the size does not
change the result, which is one live run of the image arm at both sizes to find out
([the harness](258-image-arm-injection-harness.md) is where that would go).

## Trail

- 2026-08-25: opened by the close of
  [R-399](399-the-body-edge-is-two-sites-and-no-prose.md), which read this file's `1600`s out as a
  fixture's own choice and found the docstring claiming they were not.
- 2026-08-25: **landed as the third shape, with no registry row.** Both numbers the entry names are
  what it said they are at HEAD, and the docstring's claim is wrong before either can move it: a
  capture naming no edge comes back at the body's own default and the brain names an edge of its
  own, so no capture the shipped stack takes is the corpus's size. Tracking either number was
  rejected. Registering the sentence would freeze it against a literal beside it that is free to
  leave, and tying the frame to the shipped ask would re-render every cell and break
  comparability with the published resistance matrix without anything reporting it. What replaces the claim is the argument that
  was already true and unwritten: the matrix was measured in this frame, and a payload at a fixed
  glyph size fills more of a small frame, so this is the legible end and the end a defence
  measurement should err on, which the image arm's own Chromium control already measured.
  `test_image_arm.py` carried a second copy of the old claim that this entry did not mention, and
  it is corrected too. Whether the size changes the result is unmeasured and is now
  [R-432](432-the-image-arm-has-never-run-at-two-sizes.md). The decision is the
  [ADR-0029 corpus-frame addendum](../../adr/ADR-0029-vision-screen-capture.md).
