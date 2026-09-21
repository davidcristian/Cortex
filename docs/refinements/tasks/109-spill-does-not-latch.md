# A watched spill still promises co-residency

**Status:** declined 2026-08-18
**Area:** inference-model-manager
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)

The spill watch ([R-108](108-notice-a-spilled-handoff.md)) has exactly one audience, an operator
reading the log. The proposal here was for the swap itself to react: a spill shows the
deployment's declared VRAM cost was too low, so the automatic answer would be the one a correct
declaration would have produced.

**Declined 2026-08-18** because the evidence is one handoff wide and there is no way back.

A `CadenceReading` covers one handoff, and a spill can be produced by the desktop taking a
gigabyte during a load rather than by the pair genuinely not fitting: this machine's idle floor
moves by about that much ([model-swap.md](../../runbooks/model-swap.md)), and this stack's own
measured pairing does fit, the deep model and the E4B subagent tier together at 23555 to 23642
MiB with about 908 MiB free
([docker-compose.gpu.yml](../../../docker/docker-compose.gpu.yml)). Against that, the latch is
one-way. The tier record can be repaired, because a later pass re-reads each peer's real state and
can mark it available again, but nothing can re-prove a co-resident fit once the latch has stopped
producing co-resident handoffs, since the only evidence that would clear it is the configuration
it disabled. A transient would cost every later handoff its delegation until the brain restarts.

Two of the entry's own claims were wrong. It said the automatic answer is "to evict the cortex
next time rather than run co-resident"; the cortex is stopped on every handoff regardless
([residency_moves.py](../../../brain/packages/core/src/cortex_core/residency_moves.py)), and what
`coresident` decides is whether the peer tiers are stopped as well and whether the subagent pool
is drained
([swap_conductor.py](../../../brain/packages/core/src/cortex_core/swap_conductor.py)). A latch
would withhold delegation through the handoff, not protect the cortex. It also said
`ResidencyPlan` is a frozen value with nowhere to keep the latch, which stopped being true one
day later: `SwappingModelManager` now holds `BaselineTiers`
([residency_tiers.py](../../../brain/packages/core/src/cortex_core/residency_tiers.py)), a mutable
process-lifetime residency record that already drives an automatic policy from observed evidence,
since marking a tier missing or unhosted closes GPU placement. Cost is not why this closes.

The trigger's other half is real. A second machine adopting `CORTEX_SWAP_CORESIDENT` from this
repo's numbers is already caught twice, at boot by the required `CORTEX_SWAP_BRAIN_VRAM_MIB` and
at swap time by the free-memory check before the load, and what gets past both is the
under-declaration the decode watch warns about. What is genuinely unanswered is the operator who
does not read logs, and the answer is to put the spill where the operator already looks, filed as
[R-304](304-spill-rides-the-residency-report.md).

## History

- 2026-08-08: Opened behind the spill watch, where the automatic latch was declined with its
  reason rather than merely left unbuilt.
- 2026-08-09: A trigger review of the index's fix-when-it-matters bucket read it against the tree
  and fired nothing. This entry reached that result inside a group rather than under its own name,
  the residency and model-manager entries each recent close opened, whose triggers describe a
  deployment doing something rather than a file saying something.
- 2026-08-18: Declined, with two halves of its own text corrected, and the reasoning recorded at
  the origin decision. The operator half of the trigger was refiled as
  [R-304](304-spill-rides-the-residency-report.md).
