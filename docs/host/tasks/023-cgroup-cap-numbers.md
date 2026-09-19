# The cgroup cap numbers

**Status:** never attempted
**Session:** gpu-tier-scale
**Capability:** G
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

Tag **G**, with one caveat: the tier-scale swap is the only realistic load to tune against, and that
item needs the overlay, so in practice this is measured during that session.

**What only this proves.** What leaves the machine usable.
[ADR-0012](../../adr/ADR-0012-resource-governance.md) ships the values as user-tunable placeholders,
because the 8 GB dev GPU could not hold a real tier pair, so what was validated is the mechanism and
not the arithmetic. It also warns that llama.cpp maps the GGUF into memory, so mapped model pages
count against the memory cap and a cap below the artifact size makes a load thrash rather than fail.

**Do.** Tune `CORTEX_MODELHOST_CPUS`, `CORTEX_MODELHOST_MEMORY` and `CORTEX_MODELHOST_MEMSWAP` in
`docker/docker-compose.gpu.yml`, plus the CPU subagent container's set, against a real swap and the
user's own "is this machine still usable while gaming" bar.

**Pass.** Numbers that hold under the swap's load without thrashing.

**Fail.** A load that thrashes points at a memory cap below the artifact size, which is the
documented trap above.

**Know this going in.** There is no per-model cap. The cortex, the deep model and any GPU subagent
share one cgroup, because the model host runs them as children of one container; a per-model cap
would need a container per model, which would need a controller that can start containers, which is
the docker-socket design ADR-0030 rejected on security grounds.

**Record it.** The compose file's own comment (which says the maintainer measures real numbers on
the 24 GB machine), [modules/brain-model-manager.md](../../modules/brain-model-manager.md) (which
calls them user-tunable placeholders), the readings record under
[docs/readings/](../../readings/README.md) that ADR-0012 rests on, and ADR-0012 edited in place
where the numbers change what it states.

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
