# Cross-loop salience across a batch

**Status:** open, fix when it bites
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Trigger:** A batch of subagents handed one instruction.

This item has no bullet of its own in the area doc. It was recorded inside the entry for salience
on the tool loop, in the list of items remaining behind the same seam:

> **cross-loop salience** for a batch of subagents handed one instruction, which would need a
> different justification than this policy's

The policy it would extend is per loop rather than per turn, and deliberately: "**Per loop, not
per turn, the opposite of the budget and deliberately**: the pool bounds reach, a resource the
turn's subagents share, while a repeat is redundant only against the `working` messages holding
its answer, which a sibling cannot see."

## Trail

- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing. Everything left open in that bucket is live-observation shaped, its trigger being a
  deployment doing something rather than a file saying something.
