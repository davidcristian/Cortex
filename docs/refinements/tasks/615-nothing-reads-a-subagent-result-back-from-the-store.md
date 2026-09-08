# Nothing reads a subagent result back from the store

**Status:** open, actionable
**Area:** resource-governance
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)

Opened 2026-09-08 by the close of
[R-614](614-a-refused-spawn-reaches-no-log-line.md), which re-derived the task record's lifetime and
found, on the way, that half the record has no reader.

`TaskStore.get_result` has no production call site. The cortex is handed the batch's aggregate in
memory by `SpawnSubagentsTool`, which builds it from the `SubagentResult`s `asyncio.gather` returns
rather than from Redis, so `put_result` writes a document that only a test and an operator with
`redis-cli` ever read. The port's own docstring in
`brain/packages/core/src/cortex_core/ports_stores.py` says `get_result` "returns it for the cortex
to read", and [brain-core.md](../../modules/brain-core.md) repeats the port. Both describe a read
that does not happen.

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
the port's contract and the module doc to say what the store is actually for, which costs a
paragraph and leaves the port as it is. The larger is to give the result half its reader: a
delegating turn that survives an orchestrator restart would find its subtasks' results in the store
and finish rather than re-spawn, which is the resume path the docstrings already describe and
nothing implements. The second subsumes the first, so the cheap repair is worth doing only if the
resume path is not being built soon.

## Trail

- 2026-09-08: opened by the close of
  [R-614](614-a-refused-spawn-reaches-no-log-line.md), recorded in the
  [ADR-0012](../../adr/ADR-0012-resource-governance.md) record-lifetime addendum, which traced
  every read path either key has while settling whether the record outlives its own admission wait.
