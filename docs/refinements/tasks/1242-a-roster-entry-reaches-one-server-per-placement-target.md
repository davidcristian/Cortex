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

1. **The CPU servers are still one server of two slots, and the first draw is against splitting
   them.** `llama-subagent` in `docker/docker-compose.subagents.yml` and `llama-subagent-qwen` in
   the roster file each start with `--parallel ${CORTEX_SUBAGENTS_PARALLEL:-2}` under the whole
   budget's caps (ADR-0018 decision 9). Drawn 2026-11-18
   ([readings](../../readings/subagent-budget.md#a-cpu-server-at-two-threads-against-four)): a
   server of two threads under a 4 GiB cap wrote at 0.59 of the rate of one of four threads, where
   each of two busy slots of the four-thread server writes at 0.69 to 0.75, and a server holds
   6,909 MiB in its cgroup with its weights resident, so 4 GiB each keeps under a third of the
   file in memory. Steps:
   - Draw the row that decides it, on the CPU image under `--cpuset-cpus`: two servers at once,
     `--cpus 2.0 --threads 2` each on two cores of its own, both busy, three seeds, with no
     memory cap and under 4 GiB each, against one server of two busy slots at `--threads 4`.
     Rule, written before that row: if each of the two busy servers writes below each of the two
     busy slots, this item closes as declined and the CPU servers stay one server of two slots.
     If not, the choice is between a lone subagent at its full rate (slots) and a drafter for
     every subagent (servers), and it waits for R-1239 to give the CPU tier a drafter.
   - If servers are chosen, give each its own caps. Compose cannot divide, so this needs two
     variables, for example `CORTEX_SUBAGENTS_SERVER_CPUS` (2.0) and
     `CORTEX_SUBAGENTS_SERVER_MEM_GB` (from the capped row, not the 4 first proposed), read by
     `cpus`, `--threads`, `mem_limit` and `memswap_limit`, counted in
     `scripts/subagentcouplings.py`, with decision 9 edited in place.
   - Add `llama-subagent-2` with the first server's image, flags and mounts, list both addresses
     in the `CORTEX_SUBAGENTS_ENDPOINT` default, set the `CORTEX_SUBAGENTS_PARALLEL` default to 1,
     and decide whether the alternate entry gets a second server too. `flagcheck.py` reads a new
     service from its model variable; prove it by removing a flag from the new one.
2. **The tier names no drafter**, so the main reason for the default has no effect until
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
  list differ in number. The container's stop period went from 45 to 55 s, a grace for each of
  the four default children. A first CPU draw found a server of two threads at 0.59 of the rate
  of one of four and no room for its weights under 4 GiB, so the CPU item now starts with the row
  that decides it. The two items above remain.
