# A GPU-placed subagent beside a resident cortex

**Status:** done 2026-08-04
**Sitting:** gpu-tier-scale
**Capability:** G
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

A spawn was placed on the hosted `-ngl 99` tier while the 12B cortex stayed resident and kept
serving, and the ledger accounted for it, which is this item's pass line met. The finding is a
numbers one, which is the failure this item predicted for itself.

**The measurement has left this directory**, per [index.md](../index.md)'s exit contract: its home is
the dated fit-test addendum in [ADR-0012](../../adr/ADR-0012-resource-governance.md), with the
co-residency figures in the measured table of
[runbooks/llamacpp-gpu.md](../../runbooks/llamacpp-gpu.md) and the procedure in
[runbooks/subagents-cpu.md](../../runbooks/subagents-cpu.md) section 2c. Only the heading and this
record stay, because the dependency chain above lists this item by number.

**What it found, in one paragraph.** The card holds both tiers with a third of itself to spare:
10022 MiB of `nvidia-smi` total used with the cortex resident at 16K with its projector, 13353 MiB
with the GPU-placed subagent tier beside it, and 11110 MiB still free. So the fit question this item
was written to answer turned out to be a question about the shipped numbers rather than about the
card. The placeholder pair sums to 16.8 GB (an 11.3 GB cortex reservation and a 5.5 GB subagent ask)
against a 14 GB soft cap the two tiers very nearly meet as measured: 13353 MiB of total used is
14.00 GB, of which 12.02 GB is the tiers themselves above the 1888 MiB the card reads with both
stopped. So what refused every placement was the arithmetic and not the hardware: the reservation
runs about 0.8 GB above what this build of llama.cpp needs for the cortex, and the ask about 2 GB
above what the subagent tier measured (3.48 GB). The more interesting failure this item named did
not happen either: with both tiers generating at once the cortex fell from 71.82 to 50.54 tok/s and
the subagent from 96.96 to 63.50, which is contention rather than degradation, and through the
spawn batch itself the cortex answered at 61.71 tok/s and its tier never left READY.

**Both halves of that arithmetic were corrected within four days, which is this item's finding
being acted on rather than revised.** The cortex reservation went to 8.6 GiB on 2026-08-07,
measured at the shipped tier shape and covering a peak rather than an idle reading, and the
subagent ask to 3.5 GiB on 2026-08-08, measured on this tier with the floor bracketed at both ends
of the session. So the pair claims 12.1 GB where it claimed 16.8, the shipped 14 GB soft cap holds
both, and a spawn is GPU-placed on the shipped stack for the first time. The paragraph above is
kept as the record of what the numbers were when this item closed.

**What it deliberately did not do**, both named because this item's own recipe asked for them.
`CORTEX_SWAP_EVICT_MODELS` was left unset: what it buys is a handoff stopping the tier before the
deep model loads, which is items 2 to 4's territory and needs the overlay they wait on. And the
spawn came from the live delegation suite invoking the spawn tool directly, which is what this
item's own opening blessed as a placement without a desktop, rather than from a cortex that decided
to delegate inside a turn.

## Trail

- 2026-07-19: Filed here alongside the cap numbers, both taken from inside a landed
  resource-governance entry and neither ever counted there. The ledger correction that produced
  them replaced a line reading that nothing of that area's trio remained: what the model-host
  sub-slice had validated was the runtime's mechanism, in Docker on the dev GPU with two small
  artifacts, and neither real GPU-placed subagent validation nor the placeholder cgroup numbers
  were part of it. This item never depended on the deep-model pick.
- 2026-07-19: Split back the same day. The filing's reason, that a GPU placement needs a card
  holding the cortex first, assumed the dev GPU cannot hold the cortex, and it can, so the placer's
  GPU arm firing against a real placement returned to the agent's list and what stayed here was the
  fit test beside a resident cortex, priced on that card holding the cortex with roughly 470 MiB to
  spare.
- 2026-08-04: Both halves closed together, because firing the arm with the cortex up is the
  placement beside it, and the split dissolved with them: the 470 MiB was the 8 GB card's remainder
  and not this one's, so the run kept the cortex resident and the placement beside it was simply
  what happened. The third item to leave this directory, and the one whose split turned out not to
  matter. The refinements index records the agent-side half of the same run as both placer verdicts
  witnessed against live tiers by `test_subagent_gpu_live.py`.
- 2026-08-07: The host index corrected its own reasoning about the 11.3 GB cortex figure this item's
  placeholder arithmetic rested on, in the paragraph withdrawing this sitting's eighth item. That
  figure was `nvidia-smi` total used with the desktop's own floor inside it, taken on a different
  llama.cpp build, and an idle reading where the reservation it feeds has to cover a peak.
  Re-measured at the shipped tier shape, the cortex reads 8400 to 8484 MiB idle and 8573 MiB at its
  peak above a bracketed floor, which is where the 8.6 figure comes from.
