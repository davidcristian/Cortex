# Salience on the tool loop

**Status:** done 2026-07-14
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The third and last bound of the rate policy, and the one about whether a call is worth making
rather than how many or how much. Three wastes were bounded only by the pool of 32: the same call
twice in one round, which cannot inform anything because the model chose both before seeing either
result; the same call every round; and the one that mattered, a refused call that needs
confirmation being retried. Confirmation is asked per dispatch, so nothing but the budget stopped
a model re-emitting a refused `send_email` from putting up to 32 approval cards in front of the
user for one action.

`RepeatSalience`, a pure `SaliencePolicy` port in `tool_salience.py`, admits a call unless an
identical one (same `name` and `arguments`) already ran in this round, or already ran twice in
this loop. A policy that predicts whether a call will help was rejected outright, being a model
judgement placed inside deterministic code.

Two rather than one, because the failures are asymmetric: a limit of one denies information, since
the re-read after a write returns the stale listing, while allowing two wastes at most one
dispatch. Attempts are counted rather than answers, which an earlier draft had backwards: a denial
and a declined confirmation are `is_error` results too, so counting successes would have left the
card spam this entry exists for untouched. The refusal reuses the budget's own machinery, issued
by the dispatcher, recorded in the audit and visible to the model, and it is checked before the
budget is charged, so a repeat costs nothing, and ahead of the confirmation step, which is what
turns those 32 cards into at most two.

Per loop rather than per turn, the opposite of the budget and deliberately so: the pool bounds
reach, a resource the turn's subagents share, while a repeat is redundant only against the
`working` messages holding its answer, which a sibling cannot see.

Two costs were not predicted and both were real. Ruff's argument limit made a third declaration
impossible as a seventh parameter, so `gated_names`, `costs` and `salience` became one
`DispatchPolicy`, which is the better grouping anyway. And `over_budget: bool` became
`refusal: DispatchRefusal | None` rather than growing a second parallel boolean.

`CORTEX_TOOLS_SALIENCE=off` (`AlwaysSalient`) is the loop exactly as it was before the policy, but
the default is on, because a bound that ships off has no effect until someone turns it on.
Covered at 100% with twelve guards each reverted individually, including the pair that checks the
other direction: the fixture whose forty repeats cost a pool of two dispatches with the policy on
and close that same pool with it off.

Four things were left behind it: argument identity is structural, so two ways of writing one
intent are two calls ([R-043](043-structural-argument-identity.md)); a per-round cap on distinct
calls, the one form neither bound closes ([R-042](042-per-round-call-cap.md)); a configurable
limit if two proves wrong ([R-040](040-a-configurable-limit-for-the-salience-policy.md)); and salience across the loops of
one batch ([R-041](041-cross-loop-salience.md)).

## History

- 2026-07-14: Recorded in ADR-0009 decision 12.
