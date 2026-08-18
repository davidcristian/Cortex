# A watched spill still promises co-residency

**Status:** declined 2026-08-18
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Opened 2026-08-08 by the spill watch's own landing
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) spill-watch addendum). The watch has exactly one
actor, an operator reading the log, and the obvious second one is the swap itself: a spill proves
the deployment's declared VRAM cost was too low, so the automatic answer would be the one a correct
declaration would have produced.

**Two corrections first, because half of this entry's written reasoning has expired and a close
that restated it would mislead the next reader.**

The entry says the automatic answer is "to evict the cortex next time rather than run co-resident".
That is not what the flag does. The cortex is stopped on **every** handoff, unconditionally
([residency_moves.py](../../../brain/packages/core/src/cortex_core/residency_moves.py)); what
`coresident` decides is whether the *peer* tiers are stopped as well and whether the subagent pool
is drained ([swap_conductor.py](../../../brain/packages/core/src/cortex_core/swap_conductor.py)).
A latch would therefore withhold delegation through the handoff, not protect the cortex.

The entry's cost argument, that `ResidencyPlan` is a frozen value "with nowhere to keep the latch",
stopped being true one day after it was written. `ResidencyPlan` is still frozen, but
`SwappingModelManager` now holds `StandingTiers`
([residency_tiers.py](../../../brain/packages/core/src/cortex_core/residency_tiers.py)), a mutable
process-lifetime residency record that the seam reads through `note_on` and that already pulls an
automatic policy lever off observed evidence: marking a tier missing or unhosted closes GPU
placement. The home this entry says does not exist was built on 2026-08-09. Cost is not why this
closes.

**What decides it is the evidence and the absence of a way back.** A `CadenceReading` is one
handoff wide, and a spill can be produced by the desktop taking a gigabyte during a load rather
than by the pair genuinely not fitting: this machine's idle floor moves by about that much
([model-swap.md](../../runbooks/model-swap.md)), and this stack's own measured pairing does fit,
the deep model and the E4B subagent tier together at 23555 to 23642 MiB with about 908 MiB free
([docker-compose.gpu.yml](../../../docker/docker-compose.gpu.yml)). Against that, the latch is
one-way. The tier record heals because a sweep re-reads each peer's real state and can mark it
standing again; nothing can re-prove a co-resident fit once the latch has stopped producing
co-resident handoffs, because the only evidence that would clear it is the configuration it
disabled. So a transient would cost every later handoff its delegation until the brain restarts,
on evidence that cannot be rechecked.

**The trigger's other half is real, and the answer to it is not this.** A second machine adopting
`CORTEX_SWAP_CORESIDENT` from this repo's numbers is already caught twice, at boot by the required
`CORTEX_SWAP_BRAIN_VRAM_MIB` and at swap time by the free-memory check before the load, and the
residue that gets past both is exactly the under-declaration the decode watch warns about. What is
genuinely unanswered is the operator who does not read logs, and the fix for that is to put the
spill where the operator already looks rather than to latch a feature off, which is filed as
[304](304-spill-rides-the-residency-report.md).

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
- 2026-08-18: Declined, and two halves of the text above are corrected rather than repeated: the
  latch would withhold the peers and the drain rather than the cortex, which is evicted on every
  handoff, and the "nowhere to keep it" cost died the day after this was written, when the standing
  tier record landed as exactly such a home. What carries the close is that the evidence is one
  handoff wide on a machine whose idle floor moves by a gigabyte, and that the latch has no heal
  path. The operator half of the trigger is refiled as
  [304](304-spill-rides-the-residency-report.md), and the reasoning is recorded at the origin
  decision.
