# Give the placer a model of the handoff window

**Status:** done 2026-08-07
**Area:** inference-model-manager
**Origin:** [ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md)

`VramBudgetPlacer` fit-tests every GPU-placed spawn against
`soft_cap_gb - cortex_reservation_gb - placed_gb`
([placer.py](../../../brain/packages/core/src/cortex_core/placer.py)), and during a handoff both
named terms are wrong: the cortex whose 11.3 GB is reserved has been evicted, and the deep model
holding 19 GB of the card is not charged at all, because it is not placed through the placer.
ADR-0030 decision 8 suspends the soft cap for the handoff window in prose, and nothing in code
read it. This was unreachable while the pool was drained; co-residency is what makes it reachable.

**Closed 2026-08-07**, the same day it opened
([ADR-0055](../../adr/ADR-0055-co-residency-and-spill-watch.md) decision 3, with the port half at
[ADR-0012](../../adr/ADR-0012-resource-governance.md) decision 13). It was taken rather than left
on its trigger because that trigger is a machine setting rather than a code change: any
deployment that raises `CORTEX_VRAM_SOFT_CAP_GB` far enough to admit a GPU-placed spawn reaches
it.

`SubagentPlacer` gained `charge_handoff(resident_gb=...)` and `charge_standing()` (moved to
`ports_placement.py` for the line cap and re-exported, so no call site moved), written by the
residency scope at the two edges of the swap
([residency_charge.py](../../../brain/packages/core/src/cortex_core/residency_charge.py)). What is
charged is the deployment's declared `CORTEX_SWAP_BRAIN_VRAM_MIB`, converted once through
`ResidencyPlan.brain_vram_gb`, rather than a fresh reading through the `device_memory()` verb the
fit check added. `place` is synchronous and lock-free by design, so that a batch of concurrent
spawns races the ledger correctly, and a reading there would put an HTTP call to the sidecar
inside every spawn's fit-test while buying accuracy the swap has already bought.

The charge is written before `swap_in` runs, so it applies while the fit check reads the card and
while the weights load, which closes the gap that check cannot see on its own: a spawn admitted
into the very headroom the reading just measured. The reversal waits for the far edge and happens
only once the cortex is serving again, so a restore that failed and reported it keeps charging the
deep model and keeps spawning on the CPU.

It is off unless the deployment declared a figure: with `brain_vram_mib` at its shipped zero the
window is never entered, because charging nothing would be worse than before, crediting the
evicted cortex's 11.3 GB back while the deep model holds the card.

Measured live through the real sidecar and a real residency change on the 24 GB card: 15061 MiB
free of 24463 with the cortex resident, 19553 MiB free inside the window, the charge 18.68 GiB and
the headroom 4.32 GiB against the 5.5 GiB ask shipped that day (remeasured to 3.5 on 2026-08-08,
which does not move this reading). The same spawn goes to the GPU outside the window, to the CPU
inside it, and to the GPU again after the restore
(`test_a_real_swap_charges_the_placer_for_the_model_that_holds_the_card`, which declares the deep
tier's measured cost and starts the cheap peer tier in its place).

Two limits, stated as narrowly as the fit check states its own. It charges a declared number, so a
deployment that under-declares is admitted against room it does not have, which is
[R-108](108-notice-a-spilled-handoff.md)'s subject. And a spawn onto an already-resident tier
allocates nothing (23639 MiB generating against 23642 idle), so refusing it costs decode speed
rather than correctness, and the ledger charging per spawn for an already-running tier is an older
modelling gap this entry never claimed to close. Placement-aware charging stays declined in
[resource-governance.md](../index.md#resource-governance), on the same second-GPU-executor trigger.

## History

- 2026-08-07: Opened by the co-residency close as the second of the two refinements it left
  behind, filed as fix-when-it-matters while nothing could make it matter.
- 2026-08-07: Closed a few hours later and the area went 8 to 7, one out and none in. Both of its
  claims about the code were checked first and both held, the port change included, which is the
  claim this area has twice got wrong. The index's fix-when-it-matters bucket never had a line for
  this entry, so a reader finding none removed there is seeing an omission rather than a close
  that missed one.
- 2026-08-07: One further reason was recorded for charging the declared figure rather than reading
  the card: `place` is synchronous and lock-free, and a `device_memory()` call there would have
  put HTTP inside that fit-test.
