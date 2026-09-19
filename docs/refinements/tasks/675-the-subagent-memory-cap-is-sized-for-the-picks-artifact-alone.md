# The subagent memory cap is sized for the pick's artifact alone

**Status:** open, waiting for its trigger
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-19
**Trigger:** a deployment that names a `CORTEX_MODEL_FILE_SUBAGENT` or
`CORTEX_MODEL_FILE_SUBAGENT_QWEN` artifact larger than about 5.6 GB, or that raises
`CORTEX_SUBAGENTS_MAX_TOKENS` or `CORTEX_SUBAGENT_CTX_SIZE` above their shipped defaults, on a
container still capped at `CORTEX_SUBAGENTS_MEM_BUDGET_GB` 8.

The CPU subagent servers run under `mem_limit` and `memswap_limit` of 8,589,934,592 bytes, the hard
twin of the brain's `DEFAULT_MEM_BUDGET_GB`. Under three delegated batches at the shipped 1024-token
cap that cgroup held `file` at 5,157,056,512 bytes, which is the pick's artifact at 5,154,941,280
bytes on the mount plus a little, and `anon` at 2,814,812,160, for a peak of 8,007,458,816 and
0.54 GiB of headroom. Nothing was reclaimed: `memory.events` read `max 0` and `oom_kill 0` and
`workingset_refault_file` stayed at 0. So the cap fits this artifact with about half a gigabyte to
spare, and the two settings that spend that half gigabyte are the artifact a deployment names and
the context the server allocates for its slots.

**Why it is not acted on now.** Both shipped artifacts fit. The roster alternate is Qwen3.5-2B at
Q4_K_M, which is smaller than the pick, and no lineup entry the subagent tier is offered is larger
than the pick. Raising the cap changes the deployment's admission arithmetic, since the cgroup
number is the hard twin of the soft budget the scheduler admits against and the constant scan checks
every place either is written, so it is one retune across two files and a brain constant rather than
one number.

**What would settle it.** Either a reading of a larger subagent artifact under the same cap, which
says how much of the headroom a bigger pick spends, or a decision that the cap is sized per
deployment rather than shipped, which is the memory-cap change's to revise.

## History

- 2026-09-15: opened by the close of
  [R-629](629-the-picks-cpu-server-reaches-its-memory-cap-under-the-harnesss-budget.md), from the
  delegated reading published in the delegated-memory reading of 2026-09-15
  ([model lineup](../../readings/model-lineup.md)).
- 2026-09-19: checked against the tree, and none of the three settings has moved. The two artifacts
  the CPU servers default to are the pick at 5,154,941,280 bytes and the Qwen alternate at
  1,280,835,840 on the mount, `CORTEX_SUBAGENT_CTX_SIZE` still defaults to 8192 in both files,
  `DEFAULT_SUBAGENT_MAX_TOKENS` is still 1024, and both containers are still capped at
  `CORTEX_SUBAGENTS_MEM_BUDGET_GB` 8. The token clause could not fire through compose when this
  entry was written: no compose file named `CORTEX_SUBAGENTS_MAX_TOKENS` until the 2026-09-17
  settings pass-through, which now hands the brain a host value by name and leaves the default in
  `cortex_core/subagents.py`, so the shipped default the clause means is that constant. The 5.6 GB
  threshold sits about 0.14 GB under what the published peak leaves for a larger artifact at
  unchanged `anon` (8,589,934,592 less 8,007,458,816, added to the pick's size), and a larger model
  also brings a larger `anon`, so the lower figure stands.
