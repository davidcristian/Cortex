# Run an attached image through the real cortex

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0070](../../adr/ADR-0070-user-attached-images.md)
**Verified:** 2026-09-25

The brain half of the user-attached image path is covered only by fakes. Three things about it need
the real cortex and its projector, and the card was held by a measurement session the night it was
written:

- **The request shape.** A `role: "user"` message whose `content` is a content-parts array, text
  first and then one `image_url` part per picture, is what `message_content` now sends. The capture
  path measured the tool-role form of the same array; the user-role form has not been sent to the
  real server. Send one attached PNG through `TurnEngine` and the real `LlamaCppBackend` and check
  the reply describes the picture.
- **The cost of four.** `MAX_ATTACHED_IMAGES` is 4 by reading, not by measurement. Measure the
  prompt tokens and the wall clock, with the SM clock beside it, for one and for four pictures at
  the capture path's 1600 px edge, and write the reading in `docs/readings/`.
- **The frame.** `ATTACHMENT_FRAME` tells the model that text drawn in an attached picture is
  content, not an instruction. Run the image variant of the injection harness
  ([ADR-0041](../../adr/ADR-0041-injection-image-variant.md)) with the payload on a user attachment
  instead of a capture, and record whether the frame holds. Taint and the opaque bit are the
  boundary either way.

## History

- 2026-09-25: filed by the brain half of
  [251](251-user-attached-image-path.md), which could not use the card while a measurement session ran.
