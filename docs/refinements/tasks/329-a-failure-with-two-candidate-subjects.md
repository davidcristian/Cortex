# A failure that wraps two calls names neither model

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Two log lines were left attaching nothing because a field would have been a guess.
`residency_moves` restoring the cortex wraps `_stop_what_was_swapped_in(host, model)` and
`host.start(plan.cortex_model)` in one `try`, and `swap_recovery`'s boot path wraps `_clear_deep`
and `_settle_cortex` in another, so a `ModelHostError` from either block could be about either of
two models. A `model=` field on those lines would name the wrong one roughly half the time, which
is worse than the traceback an operator reads today: a wrong field is trusted, a missing one is
not.

What would close it is narrowing each block so a failure carries the model it was actually acting
on, one `try` per call rather than one per function, each with its own message. That is a small
change to control flow in two files that are already at the edge of what a reader holds in mind,
and it multiplies the failure branches each of them tests, so it was not folded into a logging
sweep. The gain is real but modest: these are boot and restore paths, where the surrounding lines
already narrow the candidates to two.

While looking, check whether the two blocks want the same treatment or only one. Boot recovery
already has a sibling line that names its model on the `ModelNotHostedError` branch, so the
asymmetry there is visible in the file; the residency restore has no such neighbour and reads as if
naming a model were simply never considered.

## Trail

- 2026-08-19: Opened by the close of
  [326](326-a-line-that-names-nothing-it-happened-to.md), which judged these two honest as they
  stand and recorded why a field would have been an invention.
