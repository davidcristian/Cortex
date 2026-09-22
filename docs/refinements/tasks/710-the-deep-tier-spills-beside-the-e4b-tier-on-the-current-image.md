# The deep tier spills beside the E4B tier on the current image

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)
**Verified:** 2026-09-22

The co-residency table in the [model-swap measurements](../../runbooks/model-swap-measurements.md)
runbook records the plain deep tier beside the gemma-4-E4B subagent tier as a fit, read on
2026-08-07 with build `b10236` and driver 610.88, the peer costing 2878 MiB and 908 MiB left free.
On 2026-09-22, on `server-cuda` `sha256:952424b09abc` (`b10680`) and driver 616.92, the E4B tier
cost 3294 to 3307 MiB, and the plain deep tier started beside it decoded at 0.36 and then 0.62 of
its solo rate, with 749 and 757 MiB more free before the load than its 19117 MiB need. So the fit
check passes the pair at the runbook's 19125 MiB and the pair spills. Every spilled start that day
read 910 to 952 MiB free at ready; that the driver holds back about that much is an assumption from
three starts. The spill watch reports both starts at a 25.0 floor. The readings are in
[co-residency](../../readings/co-residency.md).

**What would close it.** Decide what co-residency beside the E4B tier means on this card now, and
write it in the [model-swap](../../runbooks/model-swap.md) runbook, and in ADR-0055 if the decision
changes. Candidates, each checked against a fresh reading first:

- find what grew the E4B tier by about 430 MiB between the two builds (its buffers at `--parallel
  2`), and whether a flag returns it;
- measure the margin the driver keeps, loading the deep tier beside a filler of known size in steps
  and reading where decode falls, then add that margin to `CORTEX_SWAP_BRAIN_VRAM_MIB` in the
  runbook, which on this card refuses the pair on every handoff;
- state in the runbook that the pair no longer fits a 24 GB card and co-residency needs a smaller
  peer.

The same configuration spilled by different amounts in two starts, so one start does not measure
the cost.

## History

- 2026-09-22: opened by the close of
  [R-698](698-a-drafter-sized-spill-is-unmeasured-against-the-decode-floor.md), whose run read the
  pair beside its drafter case.
