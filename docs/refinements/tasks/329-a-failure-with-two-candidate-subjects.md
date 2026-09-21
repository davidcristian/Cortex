# A failure that wraps two calls names neither model

**Status:** done 2026-08-19
**Area:** inference-model-manager
**Origin:** [ADR-0051](../../adr/ADR-0051-log-line-rendering.md)

Two log lines attached nothing because a field would have been a guess. `residency_moves` restoring
the cortex wraps `_stop_what_was_swapped_in(host, model)` and `host.start(plan.cortex_model)` in one
`try`, and `swap_recovery`'s boot path wraps `_clear_deep` and `_settle_cortex` in another, so a
`ModelHostError` from either block could be about either of two models. A `model=` field would name
the wrong one about half the time, which is worse than no field at all, because an operator acts on
a field that is there.

The fix is narrowing each block so a failure names the model it was acting on, one `try` per call
rather than one per function, each with its own message. That changes control flow in two files
already at the edge of what a reader holds in mind, and multiplies the failure branches each of
them tests.

## History

- 2026-08-19: Opened by the close of [326](326-a-line-that-names-nothing-it-happened-to.md), which
  judged these two justified as they stand and recorded why a field would have been invented.
- 2026-08-19: Fixed as ADR-0051 decision 7, and both blocks were narrowed. The asymmetry this entry
  recorded argued for narrowing rather than against it: boot recovery's `ModelNotHostedError`
  branch was right about the cortex only because `_clear_deep` swallows that error one function
  away, and splitting the block makes it right by construction. `converge_residency` clears under
  one `try` that says `the model host failed while clearing the deep model at boot` with `model`
  set to the deep tier, and settles under another that keeps `the model host was unreachable during
  boot recovery` with the cortex on it; `restore_baseline` evicts under one that says `the model
  host failed while taking the swapped-in model off the card` with the handoff's own model, and
  starts and waits under another that keeps `the model host failed while restoring the cortex` with
  the cortex. Both return values, the boot bool and the restore bool, are byte for byte what they
  were. One test was added per new branch and the two existing boot cases now assert the field as
  well as the sentence, since both fail at the deep model and a check on the words alone would pass
  on a line naming the other tier. Six mutations measured over the whole brain workspace. Not
  verified live on purpose: this is pure policy over the injected port, so a bring-up would run the
  same branch through a slower host. `docs/adr/ADR-0030` and `docs/modules/brain-core.md` were
  corrected where they described the old single line. It opened
  [330](330-a-bool-loses-which-model-failed.md), the bool that loses which of the two a restore
  attempt failed on.
