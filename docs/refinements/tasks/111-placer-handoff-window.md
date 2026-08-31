# Give the placer a model of the handoff window

**Status:** landed 2026-08-07
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)

Opened 2026-08-07 by the same landing. `VramBudgetPlacer`
fit-tests every GPU-placed spawn against `soft_cap_gb - cortex_reservation_gb - placed_gb`
([placer.py](../../../brain/packages/core/src/cortex_core/placer.py)), and during a handoff both
named terms are wrong: the cortex whose 11.3 GB is reserved has been evicted, and the deep model
holding 19 GB of the card is not charged at all, because it is not placed through the placer.
ADR-0030 decision 8 suspends the soft cap for the handoff window in prose and **nothing in code
reads it**. This was moot while the pool was drained, since no placement could happen inside the
window; co-residency is exactly what makes it reachable. It is not a live defect and the reason is
measured rather than argued: a spawn admitted to a tier that is already resident allocates no new
VRAM (23639 MiB with both tiers generating against 23642 idle), so the ledger's answer changes
nothing about the card either way, and its errors are in the safe direction anyway, a refusal
falling back to the CPU backend. **What would close it:** a placement epoch, meaning the placer
told which residency it is fit-testing against so the reservation names the model that is actually
there, which is a `SubagentPlacer` port change plus a writer at the residency scope's two edges.
Its natural companion is placement-aware charging, declined-as-recorded in
[resource-governance.md](../index.md#resource-governance) and reopening on the same second GPU-capable
executor. **Trigger:** a co-resident deployment whose peer tier is started per spawn rather than
standing (which would allocate), or a second GPU-placed tier, at which point the ledger stops
being decorative.
**Closed 2026-08-07**, the same day it opened
([ADR-0030](../../adr/ADR-0030-brain-handoff.md) handoff-window addendum, with the port half at the
[ADR-0012 handoff-window addendum](../../adr/ADR-0012-resource-governance.md)), taken rather than
left on its trigger because the trigger is a machine setting, not a code change: any deployment
that raises `CORTEX_VRAM_SOFT_CAP_GB` far enough to admit a GPU-placed spawn at all reaches it,
and the entry's own "fix when it bites" was written when nothing could bite. Two of its claims
were checked against the code first and both held: `place` really does fit-test
`soft_cap - cortex_reservation - placed`, and the port really did have to change, which this
area's index warns is the claim entries get wrong. It landed as the placement epoch this text
proposed, in the shape the text proposed it, and the naming is the only departure: the verbs are
`charge_handoff(resident_gb=...)` and `charge_standing()` on `SubagentPlacer` (moved to
`ports_placement.py` for the line cap and re-exported, so no call site moved), written by the
residency scope at the two edges of the swap
([residency_charge.py](../../../brain/packages/core/src/cortex_core/residency_charge.py)). What is
charged is the deployment's declared `CORTEX_SWAP_BRAIN_VRAM_MIB`, converted once through
`ResidencyPlan.brain_vram_gb`, and **not** a fresh reading through the `device_memory()` verb the
fit check added, for a reason worth keeping: `place` is synchronous and lock-free by design, so a
reading there would put an HTTP call to the sidecar inside every spawn's fit-test and would buy
accuracy the swap has already bought, since the fit check compares that same declared figure
against the real card at the one instant a reading is evidence. The two therefore compose in one
direction: the charge is written **before** `swap_in` runs, so it is in force while the check
reads the card and while the weights load, which closes the gap the check cannot see on its own,
a spawn admitted into the very headroom the reading just measured. The reversal waits for the far
edge and fires only once the cortex is genuinely serving again, so a restore that failed and reported it
keeps charging the deep model and keeps spawning on the CPU rather than admitting GPU work onto a
card nobody can describe. **Off unless the deployment declared a figure:** with
`brain_vram_mib` at its shipped zero the window is never entered, because charging nothing would
be worse than today, crediting the evicted cortex's 11.3 GB back while the deep model holds the
card. Measured live rather than argued, through the real sidecar and a real residency change on
the 24 GB card: 15061 MiB free of 24463 with the cortex resident, 19553 MiB free inside the
window, the charge 18.68 GiB and the headroom 4.32 GiB against the 5.5 GiB ask shipped that day
(measured to 3.5 on 2026-08-08, which does not move this reading), so the
same spawn lands on the GPU outside the window and on the CPU inside it and on the GPU again
after the restore (`test_a_real_swap_charges_the_placer_for_the_model_that_holds_the_card`, which
declares the deep tier's measured cost and starts the cheap peer tier in its place, since what a
19 GB load would add is minutes rather than evidence). **What this does not do**, stated as
narrowly as the fit check states its own limit: it charges a declared number, so a deployment
that under-declares is admitted against room it does not have, which is the sibling entry above
and the same instrument lesson; and a spawn onto an already-resident tier still allocates nothing
(23639 MiB generating against 23642 idle), so refusing it costs decode speed rather than
correctness, and the ledger charging per spawn for a standing tier is the older modelling gap
this entry never claimed to close. Placement-aware charging stays declined-as-recorded in
[resource-governance.md](../index.md#resource-governance), on the same second-GPU-executor trigger.

## Trail

- 2026-08-07: Opened by the co-residency landing as the second of the two refinements it left
  behind, filed fix-when-it-bites while nothing could bite.
- 2026-08-07: Closed a few hours later on the day it opened and the area went 8 to 7, one out and
  none in, taken rather than left on its trigger because that trigger is a setting a deployment
  turns rather than an event anybody waits for. Both of its claims about the code were re-derived
  first and both held, the port change included, which is the claim this area has twice got wrong.
  Live on the 24 GB card through the real sidecar and a real residency change: 15061 MiB free of
  24463 with the cortex resident, 19553 MiB free inside the window, a charge of 18.68 GiB leaving
  4.32 GiB of headroom against the 5.5 GiB ask shipped that day. The index's fix-when-it-bites
  bucket never carried a line for this entry, so a reader finding none struck there is seeing an
  omission rather than a close that missed one.
- 2026-08-07: One further reason was recorded for charging the declared figure rather than reading
  the card: `place` is synchronous and lock-free so that a batch of concurrent spawns races the
  ledger correctly, and a `device_memory()` call there would have put HTTP inside that fit-test.
