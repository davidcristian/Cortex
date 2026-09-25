# The user-attached image path

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-25

The user attaches a picture in the overlay and asks about it. The design is
[ADR-0070](../../adr/ADR-0070-user-attached-images.md), and the brain half is built: the
orchestrator reads `UserTurn.images` (`cortex_orchestrator/attached.py`), refuses a bad one with
`SeamError{code="attachment_refused"}` before the turn starts, and `TurnEngine` sends the pixels on
the working copy of the user's message while the store keeps the text and a note. The turn is
tainted and opaque, so it records no memory and does not hand over to the deep model.

**What remains is the body half.** The overlay has no way to attach a picture, and
`body/crates/rpc/src/converse.rs` still sends `images: Vec::new()`. The overlay has to let the user
pick or paste up to four pictures, decode each one, downscale it to a 1600 px long edge, encode it
again as PNG or JPEG, and send it through the Tauri command and the bridge into `UserTurn.images`
with its `mime_type`, `width` and `height`. It has to check the same limits before sending: four
pictures, 6 MiB each, one of the three types. A `TurnEvent::Failed` with code `attachment_refused`
shows its message and keeps the draft and the pictures, so the user can remove the one named.

## History

- 2026-07-18: Recorded when the vision slice was finished, from ADR-0029's own list of deferrals.
- 2026-08-09: A costing pass corrected the entry's closing line: it is blocked by the three-layer
  invariant above rather than by scope, and it must answer the persistence question rather than
  inherit an answer.
- 2026-09-13: Checked against the code. Every claim holds, and the four citations had all moved, so
  they name symbols instead of line numbers now. Nothing reads the field: `converse_stream.py`
  takes `event.user_turn.text` and nothing else, the overlay has no attachment path, and the two
  in-code notes about this deferral point at this backlog rather than at a coming slice.
- 2026-09-25: The design became ADR-0070 and the brain half was built. Of the three invariant
  layers only `Message` relaxed, to allow images on `USER`; the handoff snapshot and both session
  stores still refuse pixels. Filed [730](730-run-an-attached-image-through-the-real-cortex.md)
  for the live run and [731](731-refuse-an-attachment-the-cortex-cannot-see.md) for a blind
  cortex. The entry stays open for the body half.
