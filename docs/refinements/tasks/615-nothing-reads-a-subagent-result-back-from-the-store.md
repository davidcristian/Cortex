# Nothing reads a subagent result back from the store

**Status:** open, actionable
**Area:** resource-governance
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)
**Verified:** 2026-09-09

Opened 2026-09-08 by the close of
[R-614](614-a-refused-spawn-reaches-no-log-line.md), which re-derived the task record's lifetime and
found, on the way, that half the record has no reader.

`TaskStore.get_result` has no production call site. The cortex is handed the batch's aggregate in
memory by `SpawnSubagentsTool`, which builds it from the `SubagentResult`s `asyncio.gather` returns
rather than from Redis, so `put_result` writes a document that only a test and an operator with
`redis-cli` ever read. The port's own docstring in
`brain/packages/core/src/cortex_core/ports_stores.py` says `get_result` "returns it for the cortex
to read", and [brain-core.md](../../modules/brain-core.md) repeats the port. Both describe a read
that does not happen, and so do three comments in the core suite, on
`test_a_spawn_the_scheduler_refuses_becomes_a_result_not_an_exception` and
`test_a_spawn_that_waits_out_the_admission_bound_is_a_result_too` in
[test_runner.py](../../../brain/packages/core/tests/test_runner.py) and on
`test_a_subagent_that_never_stops_talking_is_stopped_at_its_deadline` in
[test_subagent_bounds.py](../../../brain/packages/core/tests/test_subagent_bounds.py). Each reads a
result out of the fake store and says `the cortex reads it back from the store`, which is the same
claim the docstring makes and is the sharper instance of it: the assertion is real and the sentence
beside it names a caller that does not exist.

`get_task` is in better shape but narrower than it reads: one production call site, in
`SubagentRunner.run`, taken once before `admit`, after which the task rides the coroutine's frame
through the wait and the attempt. So the whole of the store's traffic for one delegation is one
write per task, one read of it, and one write of the result.

**Why this matters more than a stale docstring.** The store is the one hard rule's machinery for
delegation: a subagent is a stateless function over it, so a restart or a swap mid-delegation is
supposed to lose nothing. Nothing resumes a delegation today, and it is the absent reader rather
than the store that makes that so. Until something reads a result back, the durability of the
result half is unexercised, and an operator's `cortex:task:{id}:result` key at a 3600 s TTL is the
only consumer either the docs or the design has.

**What would close it.** Two candidates, and the entry does not choose. The smaller is to repair
the port's contract, the module doc and those three comments to say what the store is actually
for, which costs a paragraph and three lines and leaves the port as it is. The larger is to give the result half its reader: a
delegating turn that survives an orchestrator restart would find its subtasks' results in the store
and finish rather than re-spawn, which is the resume path the docstrings already describe and
nothing implements. The second subsumes the first, so the cheap repair is worth doing only if the
resume path is not being built soon.

## Trail

- 2026-09-08: opened by the close of
  [R-614](614-a-refused-spawn-reaches-no-log-line.md), recorded in the
  [ADR-0012](../../adr/ADR-0012-resource-governance.md) record-lifetime addendum, which traced
  every read path either key has while settling whether the record outlives its own admission wait.
- 2026-09-09: claims held to the tree and every one of them stands. `get_result` still has no
  production call site, `get_task` still has the one in `SubagentRunner.run` taken before `admit`,
  the spawn tool still aggregates the list `asyncio.gather` returns, and `_TASK_TTL_SECONDS` is
  still 3600. What the entry undercounted is where the absent read is written down: three comments
  in the core suite say it as well as the port docstring and the module doc, so the cheap repair
  costs three test lines beyond the paragraph.
