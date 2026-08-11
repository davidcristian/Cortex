# A watched spill still promises co-residency

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** A deployment that spills repeatedly and whose operator is not reading logs, or a second machine adopting `CORTEX_SWAP_CORESIDENT` from this repo's numbers rather than its own.

Opened 2026-08-08 by the spill watch's own landing
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) spill-watch addendum). The watch has exactly one
actor, an operator reading the log, and the obvious second one is the swap itself: a spill proves
the deployment's declared VRAM cost was too low, and the correct automatic answer is the one a
correct declaration would have produced, which is to evict the cortex next time rather than run
co-resident. That was declined here on two counts and neither is a matter of effort. It latches
a working feature off on evidence one handoff wide, and a spill can be caused by the desktop
taking a gigabyte rather than by the pair genuinely not fitting, so a transient would cost every
later handoff its delegation. And `ResidencyPlan` is a frozen value handed down from the
composition root with nowhere to keep a latch, so the state would have to live on the conductor
or the controller and survive nothing, which is a residency-state question rather than a watch
one. **Trigger:** a deployment that spills repeatedly and whose operator is not reading logs, or
a second machine adopting `CORTEX_SWAP_CORESIDENT` from this repo's numbers rather than its own.

## Trail

- 2026-08-08: Opened behind the spill watch's landing, the automatic latch declined there with its
  reason rather than merely left unbuilt: it latches a working feature off on evidence one handoff
  wide, and `ResidencyPlan` is a frozen value with nowhere to keep the latch, so it is a
  residency-state question rather than a watch one.
- 2026-08-09: A trigger sweep of the index's fix-when-it-bites bucket read that bucket against the
  tree and fired nothing. This entry reached that verdict inside a group rather than under its own
  name, the residency and model-manager entries each recent close opened, whose triggers are
  live-observation shaped, a deployment doing something rather than a file saying something, so no
  reading of the code settles them.
