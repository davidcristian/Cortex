# A server per subagent is built for the GPU tier only

**Status:** done 2026-11-18
**Area:** subagents
**Origin:** [ADR-0018](../../adr/ADR-0018-heterogeneous-subagents.md)

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

The CPU servers stay one server of two slots. `llama-subagent` in
`docker/docker-compose.subagents.yml` and `llama-subagent-qwen` in the roster file each start
with `--parallel ${CORTEX_SUBAGENTS_PARALLEL:-2}` under the whole budget's caps (ADR-0018
decision 9). The rule was written before the row that decided it: if each of two busy
two-thread servers writes below each of two busy slots of one four-thread server, the CPU
servers are not split. Each busy server wrote at 0.56 of the rate of one request alone and each
busy slot at 0.67 to 0.69
([readings](../../readings/subagent-budget.md#a-cpu-server-at-two-threads-against-four)).

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
  of one of four and no room for its weights under 4 GiB. The row that decided the CPU servers
  followed: each of two busy two-thread servers wrote at 0.56 of the rate of one request alone
  on the four-thread server, under the 0.67 to 0.69 of each of its two busy slots. The CPU
  servers stay one server of two slots, and their own caps and a second CPU service are
  declined. Each GPU server starts with the drafter beside its file
  ([R-1239](1239-no-tier-but-the-deep-one-can-name-a-drafter.md)).
- 2026-11-18: the two-server default was drawn through the whole stack
  ([readings](../../readings/tier-drafters.md#the-default-stack-through-tool-turns-a-handoff-and-filled-contexts)).
  Filed from it: [R-1248](1248-with-escalation-off-nothing-starts-the-gpu-subagent-servers.md),
  [R-1250](1250-a-swap-with-an-evict-id-the-host-lacks-stops-the-cortex-before-it-fails.md) and
  [R-1251](1251-a-drafter-file-that-does-not-exist-fails-after-the-whole-model-has-loaded.md).
