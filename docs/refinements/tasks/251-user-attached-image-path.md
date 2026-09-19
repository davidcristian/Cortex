# The user-attached image path

**Status:** open, optional feature
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-13

The proto field `UserTurn.images` has existed since Slice 2 and is still ignored. Sending an image
the user attached is a different design, not a smaller version of the capture path: it travels the
other way across the gRPC boundary, has a different transport limit in a different package, is the
first place Cortex would decode an image from outside, needs a four-layer TypeScript bridge change,
and has to answer a persistence question the capture path deliberately refused, since its pixels
last only for the turn.

It is also blocked by a core invariant rather than by scope. `Message.__post_init__` raises for any
non-`TOOL` message containing images, `EscalationSlot.snapshot` refuses the same, and
`store_codec.refuse_images` refuses it again on the way to Redis, called from the session store's
`append`. A user image is therefore a deliberate relaxation of a rule asserted at three layers.

## History

- 2026-07-18: Recorded when the vision slice was finished, from ADR-0029's own list of deferrals.
- 2026-08-09: A costing pass corrected the entry's closing line: it is blocked by the three-layer
  invariant above rather than by scope, and it must answer the persistence question rather than
  inherit an answer.
- 2026-09-13: Checked against the code. Every claim holds, and the four citations had all moved, so
  they name symbols instead of line numbers now. Nothing reads the field: `converse_stream.py`
  takes `event.user_turn.text` and nothing else, the overlay has no attachment path, and the two
  in-code notes about this deferral point at this backlog rather than at a coming slice.
