# The cgroup cap numbers

**Status:** never attempted
**Sitting:** gpu-tier-scale
**Capability:** G
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

Tag **G**, with one caveat: item 2 is the only realistic load to tune against, and item 2 needs the
overlay, so in practice this is measured during that sitting.

**What only this proves.** What leaves the machine usable. Kept verbatim from
[ADR-0012](../../adr/ADR-0012-resource-governance.md):

> The values ship as user-tunable placeholders: the 8 GB dev GPU cannot hold a real tier pair, so
> what was validated is the mechanism and not the arithmetic. Note that llama.cpp mmaps the GGUF,
> so mapped model pages count against the memory cap and a cap below the artifact size makes a
> load thrash rather than fail.

**Do.** Tune `CORTEX_MODELHOST_CPUS`, `CORTEX_MODELHOST_MEMORY` and `CORTEX_MODELHOST_MEMSWAP` in
`docker/docker-compose.gpu.yml`, plus the CPU subagent container's set, against a real swap and the
user's own "is this machine still usable while gaming" bar.

**Pass.** Numbers that hold under item 2's load without thrashing.

**Fail.** A load that thrashes points at a memory cap below the artifact size, which is the
documented trap above and not a mystery.

**Know this going in.** There is no per-model cap. The cortex, the deep model and any GPU subagent
share one cgroup, because the model host runs them as children of one container; a per-model cap
would want a container per model, which would want a controller that can start containers, which
is the docker-socket shape ADR-0030 rejected on security grounds.

**Record it.** The compose file's own comment (which says the maintainer measures real numbers on the
24 GB machine), [modules/brain-model-manager.md](../../modules/brain-model-manager.md) (which calls
them user-tunable placeholders), and an ADR-0012 addendum.

## Trail

- 2026-07-19: Filed here alongside the GPU-placed subagent validation, both taken from inside a
  landed resource-governance entry and neither ever counted there, after that entry's ledger line
  was corrected from claiming nothing of the area's trio remained. When the pair was split back the
  same day and the placer's GPU arm returned to the agent's list, the cap numbers stayed host work
  unchanged.
- 2026-07-19: Recorded on the sitting's order as work the card alone can take, beside the
  deep-model pick, the injection-harness run and the GPU-placed subagent, with the swap, the chaos
  kill and the timings kept for a sitting that has the Windows desktop in the room as well, in case
  the desktop and the 24 GB card turn out to be two machines.
- 2026-08-04: The development machine was measured at 24463 MiB and the 24 GB capability stopped
  being a reason on its own to file work in this directory. The index kept this item listed anyway,
  because it is its own sitting with its own bring-up rather than because the VRAM is missing.
