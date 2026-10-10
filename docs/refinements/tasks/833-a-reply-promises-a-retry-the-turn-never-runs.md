# A reply promises a retry the turn never runs

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)
**Verified:** 2026-10-10

On the Linux shell on 2026-10-10 one of three delegated subtasks ran to the 1024-token cap and came
back as a failure whose detail ends "treat the subtask as unanswered and narrow it before delegating
it again" ([readings](../../readings/delegation-overlay.md#a-request-that-invites-delegation)). The
cortex replied "The first subagent failed to provide a summary. I will retry that specific task
while providing the answers from the other two subagents." and ended the turn: no second
`spawn_subagents` call was made, and the summary under that sentence was the cortex's own. On a
second question the cortex reported the same kind of failure accurately, with no promise.

Reproduction: the stack with the `subagents` override and the default subagent pick, the question
"Use subagents in parallel for this: one summarizes in two sentences what a lighthouse is for, one
lists three famous lighthouses, and one explains in two sentences how a lighthouse lens works."
until one subtask hits the cap (the garbled channel marker of ADR-0049 decision 10).

## What to do

Draw the cap failure several times and count promises against retries. If the promise recurs,
compare a detail that says the subtask will not be retried this turn, or one that asks the cortex
to answer the part itself and say so, against the shipped wording.

## History

- 2026-10-10: filed from the delegation flows on the Linux shell.
