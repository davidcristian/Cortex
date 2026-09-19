# The pick's CPU server reaches its memory cap under the harness's budget

**Status:** declined 2026-09-15
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)

The memory-cap reading of 2026-09-08 put the shipped subagent pick's CPU server at 90.4% of its
8 GiB limit after one 64-token completion, with `anon` at 2.58 GB, 0.77 GiB of headroom, and
`memory.events` reading `max 0`. Under the injection harness's 1600-token budget, two slots and ten
attacks per condition, every run reached the limit: `memory.peak` read `8589934592` in each,
`memory.events` counted `max` 3,720 times in the default-thread-count run and 2,874 in the second
fixed-count one, and `anon` stood at 3.19 GB. What the cap reclaims on this server is the mapped
artifact, and those pages come back through the drvfs bind: `workingset_refault_file` read 18,311
pages in the default-count run and 842 in the fixed-count one, about 72 MB and 3 MB, with 520 and 32
major faults.

That cost little, the fixed-count row decoding at 11.9 to 12.4 tokens a second with the cap binding,
and the refaulted volume is under 2% of the artifact in the worst run. The cap is the compose file's
own `mem_limit`, sized as the hard twin of the brain's soft memory budget, so raising it changes the
deployment's admission arithmetic; the reading that would justify that is one where the reclaim
costs wall clock or a kill, which none of these did.

**What would settle it.** A reading of the shipped CPU server under a delegated run at the brain's
own 1024-token cap and two slots, with `memory.events`, `workingset_refault_file` and `pgmajfault`
read off the cgroup at the end, published beside the 2026-09-08 table.

## History

- 2026-09-11: opened by the close of
  [R-627](627-the-cpu-rows-wall-clock-does-not-reproduce-the-published-one.md), which read the
  counters above while drawing its pair.
-   2026-09-12: checked against the tree, and the trigger has not fired on the one reading taken
   since. The cap is still `mem_limit` and `memswap_limit` at
   `"${CORTEX_SUBAGENTS_MEM_BUDGET_GB:-8}g"` in both CPU servers, the hard twin of
   `DEFAULT_MEM_BUDGET_GB` 8.0, and the constant scan checks every place it is written. The
   fixed-count range run read `oom_kill 0` and `workingset_refault_file` 0, where the trigger asks
   for a kill or 262,144 refaulted pages. That run also read `memory.events` `max 0`, `pgmajfault`
   279, `anon` at 3.10 GB and `memory.peak` at 8,326,414,336, which is 96.9% of the limit. So the
   server sits within a tenth of a gigabyte of the cap under ordinary summarization draws and never
   reaches it, and what reached it in the harness runs was that workload's shape rather than the
   artifact being resident: 1600 tokens across two slots and ten attacks per condition against one
   400-token request at a time.
- 2026-09-15: **declined, on the delegated reading the entry asked for.** The shipped CPU server was
  brought up from the compose stack and driven through `SpawnSubagentsTool` at
  `AttemptBounds(max_tokens=1024, timeout_s=2400.0)` with a backend per placement target, both
  resolving to that one server as the compose default does, so an admitted pair reaches it as two
  concurrent streams. Three batches, six attempts, every one stopping at the token cap:
  `memory.peak` ended at 8,007,458,816, which is 93.2% of the limit with 0.54 GiB of headroom,
  `memory.events` read `max 0` and `oom_kill 0`, `workingset_refault_file` and `pgscan` stayed at 0,
  and `pgmajfault` moved from 14 to 18. The entry's own settling condition was that the cap binds
  under this reading, and it does not. What separates it from the harness runs is the token budget
  and the attempt count, 1600 tokens over ten attacks against 1024 over two, which this run does not
  separate. The cap is charged for the whole 5.15 GB artifact plus 2.8 GB of `anon`, so it fits this
  pick and says nothing about a larger one, which is
  [R-675](675-the-subagent-memory-cap-is-sized-for-the-picks-artifact-alone.md). Published in the
  delegated-memory reading of 2026-09-15 ([model lineup](../../readings/model-lineup.md)).
