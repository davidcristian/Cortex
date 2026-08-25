# Nobody has measured whether the image arm's result depends on the picture's size

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-25 by the close of
[R-427](427-the-injection-corpus-claims-a-size-nothing-holds.md), which decided what the injection
corpus is sized on and could not decide whether the size matters.

The image arm of the injection harness renders its screens at one frame, and that frame is now
argued for rather than borrowed: the published resistance matrix was measured in it, and a payload
drawn at a fixed glyph size fills more of a small frame than of a large one, so it is the legible
end of what a screen can arrive at. Both halves of that argument are about **comparability and
conservatism**, not about the number. What neither half establishes is whether the framing's
measured resistance moves with the picture's size at all.

It plausibly could. The encoder resizes whatever it is handed onto its own grid, so a payload
occupying a smaller fraction of a larger frame arrives with fewer pixels per glyph, and the arm's
whole premise is that the model reads the instruction. If resistance is flat across the two edges
a deployment can send, the corpus's frame is a free choice and the argument for it is complete. If
it is not flat, then the number the harness publishes is a number about one resolution, and the
matrix needs a second column rather than a footnote.

**Why it was left.** The close it came out of was about a false sentence in a docstring, which
prose could fix in an afternoon. This is a live GPU run of a multimodal model over the whole
corpus in both arms, twice, and starting it inside a prose fix would have hidden the prose fix.

**What would close it.** Render the corpus at a second frame, the one a shipped deployment's ask
produces, and run the image arm at both on the shipped cortex with its projector. Publish both
matrices against each other in an addendum to the origin, whatever they say, exactly as the arm's
own number was published. Then decide: if the two agree, record that the corpus's frame is a free
choice and say so where the frame is argued for; if they do not, the corpus follows the shipped
ask and pays the re-render, and the tie to `DEFAULT_CAPTURE_MAX_EDGE` that
[R-427](427-the-injection-corpus-claims-a-size-nothing-holds.md) declined becomes worth building.
The harness to run is `brain/packages/inference/tests/test_injection_defense_live.py` with
`-k "pixels and 12B"`, which the arm's own landing note
([R-258](258-image-arm-injection-harness.md)) describes.

## Trail

- 2026-08-25: opened by the close of
  [R-427](427-the-injection-corpus-claims-a-size-nothing-holds.md), which argued the corpus's
  frame from comparability and from the attacker's benefit and found no evidence either way about
  whether the frame changes the result.
