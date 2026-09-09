# Cross-loop salience across a batch

**Status:** open, fix when it bites
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)
**Verified:** 2026-09-09
**Trigger:** A batch of subagents handed one instruction.

This item was recorded inside the entry for salience on the tool loop,
[039](039-salience-on-the-tool-loop.md), in the list of items remaining behind the same seam:

> **cross-loop salience** for a batch of subagents handed one instruction, which would need a
> different justification than this policy's

The policy it would extend is per loop rather than per turn, and deliberately: "**Per loop, not
per turn, the opposite of the budget and deliberately**: the pool bounds reach, a resource the
turn's subagents share, while a repeat is redundant only against the `working` messages holding
its answer, which a sibling cannot see."

The code says the same thing in two places. `RepeatSalience` in
`brain/packages/core/src/cortex_core/tool_salience.py` reads nothing but the calls it is handed,
and the list it is handed is `dispatched`, a local of `stream_tool_loop` in `tool_loop.py`. A
spawned subagent runs its own loop over its own list, so it can see neither its parent's calls nor
a sibling's, which is what makes a batch given one instruction dispatch that instruction's calls
once per member.

## Trail

- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing. Everything left open in that bucket is live-observation shaped, its trigger being a
  deployment doing something rather than a file saying something.
- 2026-09-09: claims held against the code and one sentence repaired. The entry opened by saying
  it has no bullet of its own in the area doc, which described the per-area layout the backlog
  left behind when it became one file per task, and this file is that bullet. Both quotations
  still read as written in the entry they come from, and the mechanism behind them is unchanged:
  salience is still per loop, `dispatched` is still a local of `stream_tool_loop`, and nothing
  shares it across the loops of one batch. The trigger has not fired. The one full batch of eight
  this repo has measured was given eight distinct subtasks over their own material on purpose, so
  that no two prompts shared a slot's prompt cache (ADR-0005 batch addendum), which is the
  opposite of a batch handed one instruction.
