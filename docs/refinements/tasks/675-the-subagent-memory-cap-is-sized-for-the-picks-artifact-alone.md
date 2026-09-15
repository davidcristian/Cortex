# The subagent memory cap is sized for the pick's artifact alone

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-15
**Trigger:** a deployment that names a `CORTEX_MODEL_FILE_SUBAGENT` or
`CORTEX_MODEL_FILE_SUBAGENT_QWEN` artifact larger than about 5.6 GB, or that raises
`CORTEX_SUBAGENTS_MAX_TOKENS` or `CORTEX_SUBAGENT_CTX_SIZE` above their shipped defaults, on a
container still capped at `CORTEX_SUBAGENTS_MEM_BUDGET_GB` 8.

Opened 2026-09-15 by the close of
[R-629](629-the-picks-cpu-server-reaches-its-memory-cap-under-the-harnesss-budget.md), whose
delegated reading measured what the cap is charged for.

**What is known.** The CPU subagent servers run under `mem_limit` and `memswap_limit` of
8,589,934,592 bytes, the hard twin of the brain's `DEFAULT_MEM_BUDGET_GB`. Under three delegated
batches at the shipped 1024-token cap that cgroup held `file` at 5,157,056,512 bytes, which is the
pick's artifact at 5,154,941,280 bytes on the mount plus a little, and `anon` at 2,814,812,160, for
a peak of 8,007,458,816 and 0.54 GiB of headroom. Nothing was reclaimed: `memory.events` read
`max 0` and `oom_kill 0` and `workingset_refault_file` stayed at 0. So the cap fits this artifact
with about half a gigabyte to spare, and the two knobs that spend that half gigabyte are the
artifact a deployment names and the context the server allocates for its slots.

**Why it is not acted on now.** Both shipped artifacts fit. The roster alternate is Qwen3.5-2B at
Q4_K_M, which is smaller than the pick, and no lineup entry the subagent tier is offered is larger
than the pick. Raising the cap changes the deployment's admission arithmetic, since the cgroup
number is the hard twin of the soft budget the scheduler admits against and the constant scan holds
every spelling of both, so it is one retune across two files and a brain constant rather than one
number. The reading that would justify it is one where a deployment the tree ships actually reaches
the limit, and none does.

**What would settle it.** Either a reading of a larger subagent artifact under the same cap, which
says how much of the headroom a bigger pick spends, or a decision that the cap is sized per
deployment rather than shipped, which is the memory-cap addendum's to revise.

## Trail

- 2026-09-15: opened by the close of
  [R-629](629-the-picks-cpu-server-reaches-its-memory-cap-under-the-harnesss-budget.md), from the
  delegated reading published in the
  [ADR-0004 delegated-memory addendum](../../adr/ADR-0004-model-lineup.md).
