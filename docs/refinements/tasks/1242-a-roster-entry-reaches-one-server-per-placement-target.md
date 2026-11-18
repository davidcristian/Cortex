# A server per subagent is built for the GPU tier only

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Verified:** 2026-11-18

Two subagents of one model run at the same time in two ways: as two slots of one server, which
loads the weights once, or as two servers of one slot, each with its own weights and context.

Both shapes are built for the GPU-placed tier, and a server per subagent is its default
([ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md) decision 12): the tier starts two
servers of one slot, and the 16 GB soft cap places a spawn on each
([ADR-0012](../../adr/ADR-0012-resource-governance.md) decision 14). Each endpoint setting
lists one server or several, a spawn leases one slot of the server with the most free
(`MultiServerModelManager` in `brain/packages/core/src/cortex_core/model.py`), the model host
starts `CORTEX_SUBAGENTS_GPU_SERVERS` servers of `CORTEX_SUBAGENTS_GPU_PARALLEL` slots, and both
shapes were checked on the 24 GB card
([readings](../../readings/subagent-budget.md#two-slots-against-two-servers)).

What remains, in the order to do it:

1. **The CPU servers are still one server of two slots.** `llama-subagent` in
   `docker/docker-compose.subagents.yml` and `llama-subagent-qwen` in the roster file each start
   with `--parallel ${CORTEX_SUBAGENTS_PARALLEL:-2}`. Each is capped at the whole budget (`cpus`,
   `mem_limit` and `--threads` from `CORTEX_SUBAGENTS_CPU_BUDGET` and
   `CORTEX_SUBAGENTS_MEM_BUDGET_GB`, ADR-0018 decision 9), so a second server of the default model
   under the same caps would run twice the threads the soft budget counts. Steps:
   - Draw first, on the CPU image: one subagent's rate at two threads against four, since a lone
     subagent has all four today, and one server's resident memory at an 8K slot under a 4 GiB cap.
   - Give each CPU server its own caps. Compose cannot divide, so this needs two variables, for
     example `CORTEX_SUBAGENTS_SERVER_CPUS` (2.0) and `CORTEX_SUBAGENTS_SERVER_MEM_GB` (4), read by
     `cpus`, `--threads`, `mem_limit` and `memswap_limit`, counted in
     `scripts/subagentcouplings.py`, with decision 9 edited in place.
   - Add `llama-subagent-2` with the first server's image, flags and mounts, list both addresses
     in the `CORTEX_SUBAGENTS_ENDPOINT` default, set the `CORTEX_SUBAGENTS_PARALLEL` default to 1,
     and decide whether the alternate entry gets a second server too. `flagcheck.py` reads a new
     service from its model variable; prove it by removing a flag from the new one.
2. **`stop_grace_period: 45s`** on `model-host` in `docker/docker-compose.gpu.yml` is sized for
   three children, and the default tier of two servers makes four.
3. **The tier names no drafter**, so the main reason for the default has no effect until
   [R-1239](1239-no-tier-but-the-deep-one-can-name-a-drafter.md) gives it one.

## History

- 2026-11-16: filed while drawing the model baseline, when two subagents beside the cortex were
  compared as slots and as servers.
- 2026-11-18: the user decided that both shapes stay supported and a server per subagent is the
  default. Built for the GPU-placed tier and checked live. The premise held. The remedy changed in
  one way: a slot is a lease the backend already holds for the whole stream, so no scheduler
  change was needed. The tier starts two servers by default, and the VRAM soft cap went from 14 to
  16 GB so the budget places a spawn on each; the default shape was checked live beside the
  cortex. The brain warns at boot when the GPU servers have more slots than the VRAM budget
  places spawns, and when the server count, the GPU addresses on the model host and the evict
  list differ in number. The three items above remain.
