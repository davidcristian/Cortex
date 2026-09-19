# Retry on CPU after a failed GPU placement

**Status:** done 2026-07-18
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

`place` is optimistic, and a real CUDA out-of-memory error showed up as `ok=False` with no
recovery. It shipped as one CPU re-run after a GPU-placed failure, with the re-run recorded in the
result's `detail`.

It is not keyed on an out-of-memory error. Measured on the dev GPU, a 14.4 GB model started with
`-ngl 99` on the 8 GB card does not fail at all: it spills to shared system memory under WSL2 and
serves 177 s later, so a branch keyed on that error could never run here. The trigger is any
GPU-placed attempt whose backend did not respond, which is reachable and which also mitigates the
tier-outage entry below, since every spawn placed on a tier that would not restart fails at its
backend and now re-runs on the CPU.

The retry does not fire on a malformed constrained reply, which is a property of the model rather
than of where it ran. It releases the GPU reservation before the re-run so headroom is never
misreported to a concurrent spawn, reuses the same admission and dispatch budget so it buys no
second charge, and combines the two attempts' taint. Combining taint is deliberate, because
under-reporting it costs safety rather than precision.

The entry's own worry about vacuous coverage held and is answered: the branch is proven by behaviour
(a failing GPU backend, a responding CPU one) rather than by a simulated error, and each of its
properties fails a named test under mutation.

## History

- 2026-07-15: Extracted from the roadmap's deferred-refinements section, one of this area's three
  entries blocked on the Slice 11 lifecycle.
- 2026-07-18: Closed with the model-host sub-slice, recorded at
  [ADR-0012 decision 12](../../adr/ADR-0012-resource-governance.md). It is the first entry here to
  close while contradicting its own premise, since the 14.4 GB model did not fail at all.
- 2026-08-04: Fired from a real GPU placement rather than from a failing fake for the first time,
  when the GPU test suite was made to fail deliberately by pointing the GPU endpoint at a closed
  port.
