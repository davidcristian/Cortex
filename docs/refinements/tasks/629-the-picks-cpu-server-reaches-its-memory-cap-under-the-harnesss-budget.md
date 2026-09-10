# The pick's CPU server reaches its memory cap under the harness's budget

**Status:** open, fix when it bites
**Area:** subagents
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Trigger:** a sitting of the pick's CPU row, or a delegated run on the shipped CPU server, whose
`memory.events` reads an `oom_kill`, or whose `workingset_refault_file` reaches 262,144 pages, which
is a gigabyte of the artifact re-read through the bind. Read both off `/sys/fs/cgroup` inside the
container while it runs.

Opened 2026-09-11 by the close of
[R-627](627-the-cpu-rows-wall-clock-does-not-reproduce-the-published-one.md), whose three sittings
were drawn for the thread count and read the memory cap in passing.

**What is known.** The memory-cap reading of 2026-09-08 put the shipped subagent pick's CPU server
at 90.4% of its 8 GiB limit after one 64-token completion, with `anon` at 2.58 GB and 0.77 GiB of
headroom, and read `memory.events` as `max 0`. Under the injection harness's 1600-token budget, two
slots and ten attacks per arm, every sitting reached the limit: `memory.peak` read `8589934592` in
each, `memory.events` counted `max` 3,720 times in the unpinned sitting and 2,874 in the second
pinned one, and `anon` stood at 3.19 GB. What the cap reclaims on this server is the mapped
artifact, and the reclaimed pages come back through the drvfs bind: `workingset_refault_file` read
18,311 pages in the unpinned sitting and 842 in the pinned one, about 72 MB and 3 MB, with 520 and
32 major faults. So the cap binds on this row, and tonight it cost little, the pinned row decoding
at 11.9 to 12.4 tokens a second with it binding.

**Why it is not acted on now.** The refaulted volume is under 2% of the artifact in the worst
sitting, and the cap is the compose file's own `mem_limit`, sized as the hard twin of the brain's
soft memory budget, which is a design the memory-cap addendum records and a number the constant scan
holds. Raising it changes the deployment's admission arithmetic, and the reading that would justify
that is one where the reclaim costs wall clock or a kill, which none of tonight's did.

**What would settle it.** A reading of the shipped CPU server under a delegated run at the brain's
own 1024-token cap and two slots, with `memory.events`, `workingset_refault_file` and `pgmajfault`
read off the cgroup at the end, published beside the 2026-09-08 table. If the cap binds there too,
the entry moves to actionable with the choice between a larger limit and a smaller context window.

## Trail

- 2026-09-11: opened by the close of
  [R-627](627-the-cpu-rows-wall-clock-does-not-reproduce-the-published-one.md), which read the
  counters above while drawing its pair.
