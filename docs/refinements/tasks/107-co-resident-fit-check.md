# Check that a co-resident card really holds the pair

**Status:** done 2026-08-07
**Area:** inference-model-manager
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)

`CORTEX_SWAP_CORESIDENT` is a claim the deployment makes about its own hardware, and nothing
verified it, because the brain container sees no GPU. The failure that leaves was measured the
same day ([co-residency](../../readings/co-residency.md)): a card that cannot hold the pair does
not fail the second load, it pages the overcommit to system memory and serves the deep model at
roughly half its decode rate, with `nvidia-smi` showing the same ~23.6 GB used and ~0.5 GB free
as a genuine fit.

**Closed 2026-08-07**, hours after it was opened
([ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md) decision 2), in a narrower shape
than the entry proposed. The entry suggested a check "at wiring time or at swap-in", and only the
second is accurate: what a card has free changes by the gigabyte while the machine runs, and at
boot the cortex is resident, which is not the residency the deep model loads into. Free memory is
evidence at one instant only, before the allocation and after everything the handoff means to
unload is gone, which is inside `swap_in` between the last `stop` and the `start`. The same figure
read after the load cannot tell a fit from a spill.

What shipped: `ModelHost` gained a fourth verb, `device_memory()`, answered off the sidecar's
existing `GET /health` through a `DeviceMemoryProbe` port over `nvidia-smi`, where every failure
and any second visible GPU is reported as no reading rather than a guess. The deployment declares
the deep tier's cost as `CORTEX_SWAP_BRAIN_VRAM_MIB`. `swap_in` fails with `SwapFailedError` when
the card is short or when there is no reading at all, and `CORTEX_SWAP_CORESIDENT=1` without that
figure is a boot failure on the real supervisor.

The entry's cost line was wrong: the brain still does not depend on reaching the sidecar at
wiring time, because nothing asks it anything until a swap runs.

Measured live: with the cortex resident the sidecar reported 14905 MiB free of 24463, the declared
19125 MiB did not clear it, and the swap failed in 0.03 s having started nothing. With the cortex
evicted the same call passed and loaded the deep model to `ready` in 69.24 s, leaving 3579 MiB
free. What it does not detect is recorded as [R-108](108-notice-a-spilled-handoff.md): a declared
figure nobody verified, and a spill that has already happened.

## History

- 2026-08-07: Opened by the co-residency close as the first of the two refinements it left behind.
- 2026-08-07: Closed hours later the same day and the count stayed at 8, one out and one in.
