# Check that a co-resident card really holds the pair

**Status:** landed 2026-08-07
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Opened 2026-08-07 by the co-residency landing
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) co-residency addendum). `CORTEX_SWAP_CORESIDENT` is
an assertion the deployment makes about its own hardware and nothing verifies it, because the
brain container sees no GPU: the fit is a fact about one card's free VRAM at one moment, and the
brain has no reading of it. The failure this leaves is the quiet one the same addendum measured:
a card that cannot hold the pair does not refuse the second load, it pages the overcommit to
system memory and serves the deep model at roughly **half** its decode rate, with `nvidia-smi`
showing the same ~23.6 GB used and ~0.5 GB free as a genuine fit. **What would close it:** the
sidecar reporting free and total device memory on `GET /health` (it is the process that can see
the card, and that body already carries the two stop bounds), the adapter carrying it, and a
check at wiring time or at swap-in that refuses, or logs loudly, when the deep tier's own measured
cost will not clear what is free. The cost is the one the stop-bounds entry above already prices:
the brain would then depend on the sidecar answering, which today it deliberately does not, and a
VRAM reading taken at wiring time is stale by the time a handoff runs. **Trigger:** any report of
a deep phase that is inexplicably slow on a co-resident deployment, or a second machine adopting
the flag without redoing the measurement.
**Closed 2026-08-07**, hours after it was opened
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) fit-check addendum), and the shape it landed in is
not quite the one above, for a reason the entry's own text contains. The proposed check was "at
wiring time or at swap-in", and only the second is honest: what a card has free changes by the
gigabyte while the machine runs, and at boot the cortex is resident, which is not the residency
the deep model loads into. **Free memory is evidence at one instant only, before the allocation
and after everything the handoff means to unload is gone**, which is inside `swap_in` between the
last `stop` and the `start`. That placement is what makes the check possible at all, since the
same figure read after the load cannot tell a fit from a spill. What landed: `ModelHost` gains a
fourth verb, `device_memory()`, answered off the sidecar's existing `GET /health` (a
`DeviceMemoryProbe` seam over `nvidia-smi`, with every failure and any second visible GPU
reported as no reading rather than a guess); the deployment declares the deep tier's cost as
`CORTEX_SWAP_BRAIN_VRAM_MIB`; `swap_in` refuses with `SwapFailedError` when the card is short or
when there is no reading at all; and `CORTEX_SWAP_CORESIDENT=1` without that figure is a boot
failure on the real supervisor, which is the constant half of the claim caught where it is
constant. The entry's own cost line is **wrong about the price**: the brain still does not depend
on the sidecar answering at wiring time, because nothing asks it anything until a swap runs, so
the stop-bounds entry's objection does not transfer. Measured live rather than argued: with the
cortex resident the sidecar reported **14905 MiB free of 24463**, the declared 19125 MiB did not
clear it, and the swap refused in **0.03 s** having started nothing; with the cortex evicted the
same call passed and loaded the deep model to `ready` in **69.24 s**, leaving 3579 MiB free. What
it does **not** detect is recorded as this area's newest entry, and it is the same instrument
lesson from the other side: a declared figure nobody verified, and a spill that has already
happened.

## Trail

- 2026-08-07: Opened by the co-residency landing as the first of the two refinements it left behind,
  the flag being an assertion a deployment makes about its own hardware that nothing verifies,
  because the brain container sees no GPU.
- 2026-08-07: Closed hours later the same day and the count stayed at 8, one out and one in. What
  made it buildable was the instrument warning rather than the flag: free memory is evidence at
  exactly one instant, inside `swap_in` between the last `stop` and the `start`, which rules out
  both the wiring-time reading the entry proposed and a reading taken after the load. Live on the
  same card as the morning's measurement, 14905 MiB free of 24463 refused a declared 19125 MiB in
  0.03 s having started nothing, and the same call with the cortex evicted loaded the deep model to
  `ready` in 69.24 s with 3579 MiB to spare.
