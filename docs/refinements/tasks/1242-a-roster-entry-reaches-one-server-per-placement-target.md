# A server per subagent is built for the GPU tier only

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)
**Verified:** 2026-11-18

Two subagents of one model run at the same time in two ways: as two slots of one server, which
loads the weights once, or as two servers of one slot, each with its own weights and context.

Both shapes are built for the GPU-placed tier, and a server per subagent is its default
([ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md) decision 12). Each endpoint setting
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
2. **The server count defaults to 1, not 2.** The shipped budget places one spawn on the GPU at a
   time: the 14 GB soft cap less the 8.6 GiB cortex reservation leaves room for one 3.5 GiB ask
   (ADR-0012 decision 14). A default of two servers needs a soft cap of at least 15.6 GiB, and the
   soft cap is a policy value of the user. Proposal for the 24 GB card: two servers, since both
   shapes fit the 18,177 MiB model budget beside the cortex in the readings above.
3. **Nothing compares the three settings that name the tier's servers**: the count the model host
   reads, the addresses in `CORTEX_SUBAGENTS_GPU_ENDPOINT` and the ids in
   `CORTEX_SWAP_EVICT_MODELS`. Neither does anything compare the GPU slots configured with the
   number of asks the VRAM budget places, so a server no spawn is placed on starts unreported.
4. **`stop_grace_period: 45s`** on `model-host` in `docker/docker-compose.gpu.yml` is sized for
   three children. Each further subagent server is one more child to stop.
5. **The tier names no drafter**, so the main reason for the default has no effect until
   [R-1239](1239-no-tier-but-the-deep-one-can-name-a-drafter.md) gives it one.

## History

- 2026-11-16: filed while drawing the model baseline, when two subagents beside the cortex were
  compared as slots and as servers.
- 2026-11-18: the user decided that both shapes stay supported and a server per subagent is the
  default. Built for the GPU-placed tier and checked live. The premise held. The remedy changed in
  two ways: a slot is a lease the backend already holds for the whole stream, so no scheduler
  change was needed, and the server count defaults to 1 because the shipped VRAM budget places one
  spawn on the GPU. The five items above remain.
