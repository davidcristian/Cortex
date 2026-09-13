# The `ToolActivity` wire `phase` field

**Status:** declined 2026-09-13
**Area:** email-confirmer
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

Remaining behind the same seams: a wire `phase` field if the chip ever needs completion states
(a proto + both-stub-trees change).

This was recorded inside the `ToolActivity` end-to-end entry, as the one thing left behind the
same seams when that chip landed.

**Why it is declined.** The completion state this entry was holding a place for reached the wire,
and it did not arrive as a field on `ToolActivity`. `ToolOutcome` is its own message, emitted
after a dispatch resolves and carrying the tool name and the audit trail's own verdict, and it
runs end to end: `proto/body.proto` declares it, the Rust transport lifts it into
`TurnEvent::ToolOutcome`, the overlay's `turnState.applyEvent` folds it, and `CaptureDot` renders
the difference between a screen the assistant asked to read and one it read. A surface that needs
settled states therefore already has one to read, and adding `phase` to `ToolActivity` would be a
second spelling of the same fact on the same stream. The half that is genuinely still unsettled
is the delegated one, a subagent's step surfacing as a `ToolActivity` through the progress sink
with its outcome dropped, and that half has its own entry in
[R-126](126-delegated-step-unsettled.md), declined on the ground that the side channel is best
effort and cannot promise the pairing at all. A `phase` field would not deliver it either.

## Trail

- 2026-07-12: recorded as the residue of the `ToolActivity` chip landing end to end, the wire
  field being a proto plus both-stub-trees change that the start-only emission did not need.
- 2026-08-07: the index named a delegated tool step announced and never settled, declined that
  day in [subagents.md](../index.md#subagents), as this field's sibling in the dead-until-a-consumer bucket
  and the same design space. That decline reopens on a surface that renders how a step ended for
  its own sake, a settled or failed state on the activity chip or a delegated-work panel listing a
  batch's steps.
- 2026-09-13: declined by the premise sweep, which read the seam rather than the entry.
  `ToolActivity` is still `{ tool_name, summary }` and carries no phase, but the stream beside it
  now carries `ToolOutcome`, wired through the Rust transport and the overlay's fold to the
  capture indicator. The consumer this entry waited for exists and is served by a different
  message, so the field it names is not work that remains.
