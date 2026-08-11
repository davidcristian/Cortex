# CUDA-OOM re-place on CPU

**Status:** landed 2026-07-18
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

The entry read:
"**CUDA-OOM → re-place on CPU.** `place` is optimistic; a real CUDA OOM surfaces as `ok=False`
today. Auto-recovery (re-issue a CPU-forced request) needs a real GPU to exercise, so it lands in
**Slice 11** / the host half, not the pure core (simulating it would be vacuous coverage)."
It landed as one CPU re-run after a GPU-placed failure with the re-place recorded in the result's
`detail`, which is what ADR-0030's mapping asked for, but **not** keyed on a CUDA OOM: measured on
the dev GPU, a 14.4 GB model started with `-ngl 99` on the 8 GB card does not fail at all, it
spills to shared system memory under WSL2 and serves 177 s later, so a branch keyed on an OOM
would have been unfireable here. The trigger is any GPU-placed attempt whose backend did not
answer, which is reachable and which also mitigates the sibling entry below (admission reopening
onto a tier that would not restart: every spawn placed on that tier fails at its backend, and now
re-runs on the CPU instead of only reporting). The retry does **not** fire on a malformed
constrained reply (a property of the model, not of where it ran), releases the GPU reservation
before the re-run so headroom is never misreported to a concurrent spawn, re-uses the same
admission and dispatch budget so it buys no second charge, and unions the two attempts' taint.
The entry's own worry about vacuous coverage held up and is answered: the branch is proven by
behaviour (a failing GPU backend, an answering CPU one) rather than by a simulated OOM, and each
of its properties reddens a named test under mutation.

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section, one of this area's three
  entries blocked on the Slice 11 lifecycle.
- 2026-07-18: Landed with the model-host sub-slice, recorded at the
  [ADR-0012 re-place addendum](../../adr/ADR-0012-resource-governance.md), the second of that trio to
  clear. It is the first entry here to land while contradicting its own stated premise: the recon
  measured a 14.4 GB model pinned to `-ngl 99` on the 8 GB card spilling to shared system memory
  under WSL2 and serving 177 s later, so a branch keyed on an OOM would have been unfireable and the
  trigger became any GPU-placed attempt whose backend did not answer.
- 2026-07-18: That widening is not a consolation prize but exactly the mitigation the tier-outage
  entry needed, since a tier the swap back could not restart makes every spawn placed on it fail at
  its backend.
- 2026-07-18: The union of the two attempts' taint was recorded as deliberate on the reason that
  under-reporting taint costs safety rather than precision.
- 2026-08-04: Fired from a real GPU placement rather than from a failing fake for the first time,
  when the GPU-arm suite was reddened on purpose by pointing the GPU endpoint at a closed port.
