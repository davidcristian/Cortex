# The `ToolActivity` wire `phase` field

**Status:** open, dead until a consumer
**Area:** email-confirmer
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** A chip that needs completion states.

Remaining behind the same seams: a wire `phase` field if the chip ever needs completion states
(a proto + both-stub-trees change).

This was recorded inside the `ToolActivity` end-to-end entry, as the one thing left behind the
same seams when that chip landed.

## Trail

- 2026-07-12: recorded as the residue of the `ToolActivity` chip landing end to end, the wire
  field being a proto plus both-stub-trees change that the start-only emission did not need.
- 2026-08-07: the index named a delegated tool step announced and never settled, declined that
  day in [subagents.md](../index.md#subagents), as this field's sibling in the dead-until-a-consumer bucket
  and the same design space. That decline reopens on a surface that renders how a step ended for
  its own sake, a settled or failed state on the activity chip or a delegated-work panel listing a
  batch's steps.
