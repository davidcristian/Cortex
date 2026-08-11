# The real GPU-placed runtime mechanism

**Status:** landed 2026-07-18
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

The entry read: "**The real GPU-placed runtime mechanism.** Two live `llama-server` sidecars (GPU
`-ngl 99` + CPU `-ngl 0`) in `docker/docker-compose.subagents.yml` + per-container
`--cpus`/`--memory` cgroup caps + real GPU-placed-subagent validation lands with the **Slice 11**
lifecycle behind the corrected ports." Two of the three landed as written and one moved.
ADR-0030 decision 3 relocated the GPU sidecar into the `model-host` supervisor container (the one
holding the GPU reservation and the models mount), so the GPU-placed subagent is a **hosted tier**
on :8083 with `-ngl 99`, opt-in behind `CORTEX_MODEL_FILE_SUBAGENT_GPU`, rather than a second
service in the subagents override; the CPU `-ngl 0` sidecar stays its own container as described.
**The tier is not what `CORTEX_SUBAGENTS_GPU_ENDPOINT` points at by default, and saying it was
is the one wrong claim this entry shipped with (corrected 2026-07-18).** That variable still
defaults to the CPU server (`docker-compose.subagents.yml`), which is the safe default, since a
deployment that has not named a GPU subagent artifact would otherwise route GPU-placed spawns at
a tier that answers nothing. Opting in is therefore three settings together, now written in the
gpu override's own checklist and in [subagents-cpu.md](../../runbooks/subagents-cpu.md): the
artifact file, `CORTEX_SUBAGENTS_GPU_ENDPOINT=http://model-host:8083`, and the tier's id in
`CORTEX_SWAP_EVICT_MODELS` so a handoff stops it first. The caps landed on both containers
(`cpus`/`mem_limit`/`memswap_limit`, verified applied by the runtime as `NanoCpus`/`Memory`/
`MemorySwap`), with the CPU one's defaults set to the hard twin of the brain's soft admission
budgets, which is what makes those budgets more than an honour system. **The granularity this
costs is the interpretation to know about:** the cortex, the deep model and the GPU subagent are
now processes in ONE cgroup, so no per-model CPU or RAM cap exists, only one cap set covering all
three. ADR-0030 wins as the later and more specific decision, and its security argument is what
buys it (a per-model cap would want a container per model, which is a controller that can start
containers, which is the docker-socket shape decision 3 rejected). The numbers themselves are
user-tunable placeholders: the 8 GB dev GPU cannot hold a real tier pair, so what was validated
here is the mechanism, not the arithmetic. Real GPU-placed-**subagent** validation is the one
piece still owed, and it is host-side for the same reason: a GPU-placed subagent only happens
when `CORTEX_SUBAGENTS_VRAM_GB` fits under the soft cap minus the resident cortex, which needs a
card that holds the cortex first. Consequently the `VramBudgetPlacer`'s GPU arm has never fired
against a real placement: with the shipped settings every spawn overflows to CPU.
**Index corrected 2026-07-19.** That bucket line read "Nothing of this area's trio remains here",
true of the trio's *entries* and misleading about the area, since it read as if nothing at all
were owed. It now names both halves of what is left, the subagent validation and the placeholder
cap numbers, as host-side hardware work rather than deferred design, which is why neither is
counted in this area's open items. **Both moved to
[docs/host/gpu-tier-scale.md](../../host/index.md#gpu-tier-scale) the same day**, with the sentences
above kept verbatim there; the cap numbers arrived carrying the mmap trap ADR-0012 records,
which is that a cap below the artifact size makes a load thrash rather than fail.
**The reason above is wrong in its second half, and half of that validation comes back here
(2026-07-19).** "Which needs a card that holds the cortex first" says the dev GPU does not hold
the cortex, and it does:
[ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) measured `gemma-4-12b-it-qat-q4_0.gguf`
resident with its vision projector at `-ngl 99 --ctx-size 4096 --parallel 1`, and
[ADR-0030](../../adr/ADR-0030-brain-handoff.md) records the model alone taking 7715 of that card's
8188 MiB.
What the card cannot do is hold anything *beside* that cortex, roughly 470 MiB of headroom
against a multi-GB subagent, so a GPU placement **beside a resident cortex**, which is the
arithmetic ADR-0012 cares about, stays host-side and stays item 6 of
[docs/host/gpu-tier-scale.md](../../host/index.md#gpu-tier-scale). The **mechanism** does not need a
resident cortex at all: with no cortex up, the budget sized to this card
(`CORTEX_VRAM_SOFT_CAP_GB`, `CORTEX_VRAM_CORTEX_GB`, `CORTEX_SUBAGENTS_VRAM_GB` are all env), a
small artifact in `CORTEX_MODEL_FILE_SUBAGENT_GPU` and `CORTEX_SUBAGENTS_GPU_ENDPOINT` pointed at
the sidecar's `:8083`, the `VramBudgetPlacer`'s GPU arm can fire against a real placement here and
the route from a GPU verdict to an `-ngl 99` tier can be exercised end to end. That is the same
mechanism-versus-tier-scale split the swap already uses, it is agent-side under the rule that "on
the host" includes the agent, and it is **actionable now** rather than host work. Nobody has run
it: the GPU arm has still never fired against a real placement, which is exactly why the split
matters.
**It ran on 2026-08-04 and the GPU arm has now fired ([ADR-0012 GPU-arm
addendum](../../adr/ADR-0012-resource-governance.md), procedure in
[subagents-cpu.md](../../runbooks/subagents-cpu.md)).** The stack was the base plus the gpu,
subagents and modelhost-loopback overrides, with the E4B subagent pick hosted twice: as the
sidecar's `-ngl 99` tier on `:8083` (reachable at `127.0.0.1:9083`, since the sidecar's tiers are
otherwise unpublished) and as the subagents override's `-ngl 0` CPU server on `:8082`. Both arms
are witnessed by a new integration suite,
`brain/packages/orchestrator/tests/test_subagent_gpu_live.py`, which reads the three env values
through the same settings classes the composition root reads and records which backend each spawn
was handed. With the soft cap raised to 20 GB for the card the repo is developed on (headroom
8.7 GB against the shipped 5.5 GB ask), two concurrent spawns of one roster entry landed **one on
the GPU tier and one on the CPU server**, which is the ledger doing its job rather than a
coincidence of two servers: the tier's own `llama-server` log carries exactly one task, 18 prompt
tokens at 104.83 tok/s and 4 generated at 81.07 tok/s for 221.05 ms in total, against 12536.83 ms
for the sibling that overflowed. With the shipped soft cap of 14 GB (headroom 2.7 GB, under the
same ask) both spawns overflowed and the tier's task count did not move, so the arm is proven able
to stay silent as well as to fire. **The sentence above is therefore false as of that date and is
kept as the record**; what is left of this entry's host half is the cap numbers.
**The suite was proved able to fail before it was trusted.** The same budget with the GPU endpoint
pointed at a closed port reddens on a third placement, because a GPU-placed attempt whose backend
did not answer re-runs once on the CPU, which is also the first time the re-place two bullets up
has fired from a real GPU placement rather than from a failing fake.
**The host half went with it, because the run kept the cortex resident (2026-08-04).** The
placement beside a resident cortex that this entry sent to item 6 of
[docs/host/gpu-tier-scale.md](../../host/index.md#gpu-tier-scale) is what a GPU arm firing on that stack
is, so that item closed the same day with its numbers at the
[ADR-0012 fit addendum](../../adr/ADR-0012-resource-governance.md). Its finding is about this
entry's own numbers: the card holds both tiers with 11110 MiB free and the pair costs 14.00 GB of
`nvidia-smi` total used, which is the deliberate soft cap, while the placeholders inside it claim
16.8 GB for the same pair (a cortex reservation 0.8 GB high and a subagent ask 2 GB high). So the
reason no spawn was ever GPU-placed is the arithmetic, and the lever is the cap, which is a user
policy value rather than a placer question. What is still owed of this bullet is the cgroup cap
numbers alone.

## Trail

- 2026-07-15: Extracted from the ROADMAP's deferred-refinements section, one of this area's three
  entries blocked on the Slice 11 lifecycle.
- 2026-07-18: Landed with the model-host sub-slice and in a different container than the entry
  expected, recorded at the [ADR-0012 host-half addendum](../../adr/ADR-0012-resource-governance.md)
  and the [ADR-0030 model-host addendum](../../adr/ADR-0030-brain-handoff.md). ADR-0030 decision 3
  relocated the GPU sidecar into the `model-host` supervisor container, and the per-container caps
  landed on that container and on the CPU one, verified applied by the runtime. It is the last of
  this area's three entries blocked on the Slice 11 lifecycle to clear, landing later the same day
  as the re-place, when the rest of that sub-slice went in.
- 2026-07-18: The audit round on that sub-slice corrected two records. The landing had been declared
  with two of its three required records, the area doc and the index, while its own origin ADR got
  nothing; and the claim that `CORTEX_SUBAGENTS_GPU_ENDPOINT` points at the hosted tier was false,
  so the three-setting opt-in went into the gpu override's checklist and the subagents runbook.
- 2026-07-19: The pickup-order line "Nothing of this area's trio remains here" was corrected to name
  both halves of what was left, and real GPU-placed subagent validation and the placeholder cgroup
  numbers moved to [docs/host/gpu-tier-scale.md](../../host/index.md#gpu-tier-scale) as items 6 and 7. The
  same day the validation half split back, the dev GPU holding the cortex after all, so only a
  placement beside a resident cortex stayed there.
- 2026-08-04: The `VramBudgetPlacer`'s GPU arm fired against a real placement for the first time,
  both verdicts witnessed by `test_subagent_gpu_live.py`, and host item 6 closed the same day
  because the run kept the cortex resident. Its finding is that the shipped placeholders and not the
  card are why nothing was ever GPU-placed, and the cgroup cap numbers are the only piece of this
  entry still owed.
- 2026-08-04: The claims this entry shipped with all held against the code, which the index called
  the rarer outcome for this backlog: the budget really is the three env values, the tier really is
  one artifact behind `CORTEX_MODEL_FILE_SUBAGENT_GPU`, and routing really is the separate
  `CORTEX_SUBAGENTS_GPU_ENDPOINT` setting the 2026-07-18 correction added. What the run added is the
  part no reading of the code can give.
- 2026-08-04: The mechanism-versus-tier-scale split this entry was given on 2026-07-19 dissolved
  with that run. The "roughly 470 MiB to spare" that sent a placement beside a resident cortex to
  the host backlog is the 8 GB card's remainder rather than this card's, so the run kept the cortex
  resident and the placement beside it was simply what happened.
