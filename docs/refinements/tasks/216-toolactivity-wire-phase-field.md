# The `ToolActivity` wire `phase` field

**Status:** declined 2026-09-13
**Area:** email-confirmer
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

A `phase` field on `ToolActivity` was held open in case the chip ever needed completion states, a
proto plus both-stub-trees change.

The completion state it was holding a place for reached the wire, and not as a field on
`ToolActivity`. `ToolOutcome` is its own message, emitted after a dispatch resolves and containing
the tool name and the audit record's own result, and it runs end to end: `proto/body.proto` declares
it, the Rust transport lifts it into `TurnEvent::ToolOutcome`, the overlay's `turnState.applyEvent`
folds it, and `CaptureDot` renders the difference between a screen the assistant asked to read and
one it read. So a surface that needs settled states already has one, and adding `phase` would be a
second way of writing the same fact on the same stream.

The half that is genuinely unsettled is the delegated one, a subagent's step surfacing as a
`ToolActivity` through the progress sink with its outcome dropped, and that has its own entry in
[R-126](126-delegated-step-unsettled.md), declined because the side channel is best effort and
cannot promise the pairing at all. A `phase` field would not deliver it either.

## History

- 2026-07-12: Recorded as what was left over when the `ToolActivity` chip shipped end to end.
- 2026-08-07: Named alongside a delegated tool step announced and never settled, declined that day
  in [subagents.md](../index.md#subagents). That decline reopens on a surface that renders how a
  step ended for its own sake.
- 2026-09-13: Declined by the premise review, which read the interface rather than the entry.
  `ToolActivity` is still `{ tool_name, summary }` with no phase, but the stream beside it now has
  `ToolOutcome`, wired through the Rust transport and the overlay's fold to the capture indicator.
