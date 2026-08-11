# The user-attached image path

**Status:** open, feature breadth
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

(`UserTurn.images`). The proto field has existed since Slice 2
and is still ignored. It is a genuinely different design, not a smaller version of this one: a
different seam direction, a different transport limit in a different package, the first path
where Cortex would **decode a foreign image**, a four-layer TypeScript bridge change, and a
persistence answer the capture path deliberately refused to give (pixels here are turn-local).
It lands with its own design, and the in-code notes that used to promise it "arrives with
vision" now point here instead.

## Trail

- 2026-07-18: recorded in this area when the vision slice landed, from ADR-0029's own list of
  what the slice deferred.
- 2026-07-19: the index recorded it in its pickup order with the note that nothing blocks it but
  scope, since it lands with its own design.
- 2026-08-09: a costing pass against the tree corrected the entry's own closing line. It is blocked
  by a core invariant rather than by scope: `Message.__post_init__` raises for any non-`TOOL`
  message carrying images (`conversation.py:67`, whose docstring at lines 46 to 52 calls it an
  invariant rather than a convention, so the domain cannot express the shape), the handoff record
  refuses the same (`handoff.py:174` and 181), and the session store refuses it again on the way to
  Redis (`store_codec.refuse_images` at line 58, called from `store.py:119`). A user image is
  therefore a deliberate relaxation of a rule asserted at three layers, and it must answer the
  persistence question the capture path refused rather than inherit an answer. Nothing opened and
  nothing closed, so no count moved.
