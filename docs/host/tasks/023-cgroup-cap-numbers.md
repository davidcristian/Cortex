# The cgroup cap numbers

**Status:** never attempted
**Session:** gpu-tier-scale
**Capability:** W+G
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)
**Verified:** 2026-10-07

Tag **W+G**, re-scoped 2026-10-02. The numbers themselves, measured under a real handoff, are agent
work on the 24 GB card through a client that approves the confirm card, the handoff client of
[a handoff without the overlay](../../runbooks/model-swap-measurements.md#a-handoff-without-the-overlay):
its caps row reads load time, decode rate and the cgroup's `memory.peak` at the shipped values and
below them, and sets the defaults. What stays here is the one bar no agent can read: the user's own "is
this machine still usable while gaming" judgement on the Windows desktop while a handoff runs.
The caps row drew on 2026-10-02: 21g and 19g with 8 CPUs and 24g with 4 CPUs were each safe
under its rule, and every load took at most 0.32 of `CORTEX_SWAP_LOAD_TIMEOUT_S`, so
[ADR-0012](../../adr/ADR-0012-resource-governance.md) names 19g and 4 CPUs as the measured floors
and keeps 24g and 8 CPUs as the defaults
([readings](../../readings/model-swap.md#a-handoff-through-the-conductor)).

**What only this proves.** That the values the caps row set leave the machine usable for the person at
it. [ADR-0012](../../adr/ADR-0012-resource-governance.md) ships `CORTEX_MODELHOST_CPUS`,
`CORTEX_MODELHOST_MEMORY` and `CORTEX_MODELHOST_MEMSWAP` as user-tunable values; llama.cpp maps the
GGUF into memory, so mapped model pages count against the memory cap and a cap below the artifact
size makes a load thrash rather than fail.

**Do.** Play a game on the Windows desktop while a handoff runs, started from the overlay or from
the handoff client, and lower `CORTEX_MODELHOST_CPUS` in `docker/docker-compose.gpu.yml` until the
game stays usable, within the measured floor of 4 CPUs.

**Pass.** A handoff that completes inside `CORTEX_SWAP_LOAD_TIMEOUT_S` while the game stays usable.

**Fail.** A load that thrashes points at a memory cap below the artifact size, which is the
documented trap above. A game that stutters at the caps row's values is the finding this item exists for.

**Know this going in.** There is no per-model cap. The cortex, the deep model and any GPU subagent
share one cgroup, because the model host runs them as children of one container; a per-model cap
would need a container per model, which would need a controller that can start containers, which is
the docker-socket design ADR-0030 rejected on security grounds.

**Record it.** The compose file's comment on the caps, the readings record under
[docs/readings/](../../readings/README.md) that ADR-0012 rests on, and ADR-0012 edited in place
where the user's values differ from the caps row's.

## History

- 2026-07-19: filed here alongside the GPU-placed subagent validation, both taken from inside a
  resource-governance entry and neither ever counted there. When the pair was split back the same
  day and the placer's GPU branch returned to the agent's list, the cap numbers stayed host work.
- 2026-07-19: recorded on the session's order as work the card alone can take, beside the
  deep-model pick, the injection-harness run and the GPU-placed subagent, with the swap, the chaos
  kill and the timings kept for a session that has the Windows desktop in the room as well, in case
  the desktop and the 24 GB card turn out to be two machines.
- 2026-08-04: the development machine was measured at 24463 MiB and the 24 GB capability stopped
  being a reason on its own to file work in this directory. This item stayed listed because it is
  its own session with its own bring-up rather than because the VRAM is missing.
- 2026-10-02: re-scoped to the user's usability check, and tagged W+G for it. The tier-scale
  handoff it was waiting for can be started by any client that answers the confirm card, so the
  cap numbers were drawn headless on the card that night with the handoff client; the floors
  measured, 19g and 4 CPUs, are the lower bound for the CPU value this item lowers.
