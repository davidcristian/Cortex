# Salience on the tool loop

**Status:** landed 2026-07-14
**Area:** tools-mcp
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

The third and last bound of decision 3's rate policy,
and the one about whether a call is worth making rather than how many or how much. Three
wastes were bounded only by the pool of 32: the same call twice in one round (the model chose
both before seeing either result, so the second cannot inform anything), the same call every
round, and, the one that mattered, **a declined gated call retried**, since the gate consults
the `Confirmer` per dispatch and nothing but the budget stopped a model re-emitting a refused
`send_email` from putting **up to 32 approval cards** in front of the user for one action.
`RepeatSalience` (a pure `SaliencePolicy` seam in `tool_salience.py`, the
`HistoryWindow`/`RecallPolicy` pattern) admits a call unless an identical one (same `name` and
`arguments`) already ran **in this round**, or already ran **twice in this loop**. The tempting
reading of "deserve", a policy that predicts whether a call will help, was rejected outright as
a model judgment placed inside deterministic code. Two rather than one on the asymmetry of the
failures: a limit of one denies information (the re-read after a write returns the stale
listing), allowing two wastes at most one dispatch, and preferring the benign failure is the
ADR-0025 clamp's argument again. **Attempts are counted, not answers**, which an earlier draft
had backwards: a gate denial and a declined confirmation are `is_error` results too, so
counting successes would have left the card spam this entry exists for completely untouched.
The refusal reuses the budget's own machinery (dispatcher-issued, audited, model-visible) and
is checked **before** the budget is charged, so a repeat costs nothing, and **ahead of the
gate**, which is what turns those 32 cards into at most two. **Per loop, not per turn, the
opposite of the budget and deliberately**: the pool bounds reach, a resource the turn's
subagents share, while a repeat is redundant only against the `working` messages holding its
answer, which a sibling cannot see. Two costs this entry did not predict, both real: the
ruff argument ceiling made a third declaration impossible as a seventh parameter, so
`gated_names`, `costs`, and `salience` became one `DispatchPolicy` (the honest grouping anyway,
and headroom for the next one), and `over_budget: bool` became `refusal: DispatchRefusal | None`
rather than growing a second parallel boolean. `CORTEX_TOOLS_SALIENCE=off` (`AlwaysSalient`) is
the pre-policy loop exactly, but the default is on, because a bound that ships off has no effect
until someone turns it on. CI-gated at 100% with twelve guards mutation-proven, including the counterfactual pair
(the fixture whose forty repeats cost a pool of two spends and closes that same pool with the
policy off). Remaining behind the same seam: **argument identity is structural**, so two
spellings of one intent are two calls (normalizing needs the advertised parameter schema at the
policy, and the direction is at least the safe one); **a per-round cap on distinct calls**,
the one shape neither bound closes, since a round may still append unboundedly many results or
refusals to `working` (a context-growth problem, not a reach one, and pre-existing); **a limit
knob** if two proves wrong; and **cross-loop salience** for a batch of subagents handed one
instruction, which would need a different justification than this policy's.

## Trail

- 2026-07-14: Recorded in the ADR-0009 salience addendum.
