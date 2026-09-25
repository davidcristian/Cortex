# Measure the attachment frame on the real cortex

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0070](../../adr/ADR-0070-user-attached-images.md)
**Verified:** 2026-09-25

`ATTACHMENT_FRAME` tells the model that text drawn in an attached picture is content, not an
instruction. Its effect on the real cortex is not measured. The user-role request it goes with is:
the cortex reads one and four attached pictures through `TurnEngine` and `LlamaCppBackend`
([readings](../../readings/vision-capture.md#pictures-the-user-attaches),
`test_attached_image_live.py`).

Run the image variant of the injection harness
([ADR-0041](../../adr/ADR-0041-injection-image-variant.md)) with the payload on a user attachment
instead of a capture, and record whether the frame holds. The harness sends its picture on a
`role: "tool"` message today, so the variant needs the payload moved onto the user's message with
the frame after the typed text, as `attach_images` builds it. Taint and the opaque bit are the
boundary either way.

## History

- 2026-09-25: filed by the brain half of
  [251](251-user-attached-image-path.md), which could not use the card while a measurement session ran.
