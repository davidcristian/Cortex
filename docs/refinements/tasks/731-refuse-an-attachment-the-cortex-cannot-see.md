# Refuse an attachment the cortex cannot see

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0070](../../adr/ADR-0070-user-attached-images.md)
**Verified:** 2026-09-25

A turn with an attached image reaches the model whether or not the serving cortex has a projector.
Without one, llama.cpp answers the request with an error, the turn fails as `inference_failed`, and
the user's message is already stored with its attachment note. The capture path does not have
this problem because `SightedToolRegistry` asks `VisionProbe.can_see()` before it offers or runs
`capture_screen`.

**What would be built.** The same probe in the turn: a `sight: VisionProbe | None` on
`TurnCapabilities`, and a check in `TurnEngine.handle_turn` before the user message is stored. A
blind cortex would then refuse the attachment the way a malformed one is refused, with nothing
stored, which needs a typed core error the converse stream maps to `attachment_refused` rather
than to `internal`. The probe is the part that needs design: `build_vision` makes one only when a
body gateway is configured and `CORTEX_VISION` is `auto`, because it was built for the capture
tool. An attachment arrives over `Converse` whether or not the brain can call the body, so the
turn's probe has to be built from `CORTEX_VISION` alone, with `on` and `off` answering without a
request.

## History

- 2026-09-25: filed by the brain half of
  [251](251-user-attached-image-path.md), which left the blind-model case failing as an inference
  error.
