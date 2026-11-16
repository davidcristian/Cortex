# A roster entry reaches one server per placement target

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Verified:** 2026-11-16

Two subagents of one model can run at the same time in two ways. As two slots, one server holds
both conversations and loads the weights once. As two servers, each process loads its own weights
and has its own context.

Only the first can be configured. `SubagentResources.backends` in
`brain/packages/core/src/cortex_core/roster.py` maps each `PlacementTarget` (`GPU`, `CPU`) to one
`InferenceBackend`, so a roster entry reaches at most one GPU server and one CPU server.
`CORTEX_SUBAGENTS_PARALLEL` (default 2) is the slot count of both: `--parallel` on `llama-subagent`
in `docker/docker-compose.subagents.yml`, and `subagent_gpu_parallel` on the one subagent tier the
model host starts (`tiers()` in `brain/packages/model_manager/src/cortex_model_manager/config.py`).

A second roster entry on another endpoint is not a second server of the default model. It has its
own advertised name, the cortex chooses it per spawn, and `SubagentRoster.resolve` sends every
tainted or tool-enabled spawn to the default entry.

What the two shapes trade:

- **Memory.** A second server costs the whole footprint again: 3,131 MiB on the card for
  gemma-4-E4B at a 4K context without a drafter, measured 2026-11-16. A second slot adds only its
  context.
- **Features limited to one slot.** The Qwen cards say multi-token prediction does not support
  more than one slot (decision 5 of [ADR-0077](../../adr/ADR-0077-model-card-settings.md)), and
  the gemma cards do not say. A server per subagent keeps the drafter in both cases. The two-slot
  case is drawn under [R-1239](1239-no-tier-but-the-deep-one-can-name-a-drafter.md).
- **Failure.** A crash or a restart of one server stops both of its slots. With two servers it
  stops one subagent.

What would close it: a server count per placement target on a roster entry, or a list of
endpoints, which the model host's subagent tier and the compose files follow; a scheduler that
admits a subagent to a server with a free slot; VRAM and CPU budgets that count every server;
`flagcheck.py` and `settingscheck.py` reading the added servers; and a draw of two slots against
two servers, both busy, for rate and memory. Both shapes stay supported. The intended default is
two servers, when that draw and the memory budget allow it.

## History

- 2026-11-16: filed while drawing the model baseline, when two subagents beside the cortex were
  compared as slots and as servers.
