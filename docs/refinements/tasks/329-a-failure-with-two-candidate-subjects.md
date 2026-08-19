# A failure that wraps two calls names neither model

**Status:** landed 2026-08-19
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
- 2026-08-19: Landed as the ADR-0038 narrowed-block addendum. The open question was answered
  against the code and **both** blocks were narrowed. The asymmetry this entry noticed turned out
  to argue for narrowing rather than against it: boot recovery's `ModelNotHostedError` arm was
  right about the cortex only because `_clear_deep` swallows that error one function away, and
  splitting the block makes it right by shape. So `converge_residency` clears under one `try` that
  says `the model host failed while clearing the deep model at boot` with `model` set to the deep
  tier, and settles under another that keeps `the model host was unreachable during boot recovery`
  with the cortex on it; `restore_standing` evicts under one that says `the model host failed while
  taking the swapped-in model off the card` with the handoff's own model, and starts and gates
  under another that keeps `the model host failed while restoring the cortex` with the cortex. Both
  verdicts, the boot bool and the restore bool, are byte for byte what they were. One test was
  added per new branch and the two existing boot cases now assert the field as well as the
  sentence, since both of them fail at the deep model and a check on the words alone would pass on
  a line naming the other tier. Six mutations were measured over the whole brain workspace, which
  is the table in the addendum. Not verified live on purpose: this is pure policy over the injected
  port, so a bring-up would run the same branch through a slower host. `docs/adr/ADR-0030` and
  `docs/modules/brain-core.md` were corrected where they described the old single line. What it
  opened is [330](330-a-bool-loses-which-model-failed.md), the bool that loses which of the two a
  restore attempt failed on.
