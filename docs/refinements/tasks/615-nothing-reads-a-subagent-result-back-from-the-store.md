# Nothing reads a subagent result back from the store

**Status:** done 2026-09-10
**Area:** resource-governance
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)

`TaskStore.get_result` had no production call site. The cortex is handed the batch's aggregate in
memory by `SpawnSubagentsTool`, which builds it from the `SubagentResult`s `asyncio.gather` returns
rather than from Redis, so `put_result` wrote a document that only a test and an operator with
`redis-cli` ever read. The port's docstring in
`brain/packages/core/src/cortex_core/ports_stores.py` said `get_result` "returns it for the cortex
to read", and three comments in the core suite said the same: on
`test_a_spawn_the_scheduler_refuses_becomes_a_result_not_an_exception` and
`test_a_spawn_that_waits_out_the_admission_bound_is_a_result_too` in
[test_runner.py](../../../brain/packages/core/tests/test_runner.py), and on
`test_a_subagent_that_never_stops_talking_is_stopped_at_its_deadline` in
[test_subagent_bounds.py](../../../brain/packages/core/tests/test_subagent_bounds.py).

`get_task` has one production call site, in `SubagentRunner.run`, taken once before `admit`, after
which the task stays in the coroutine's frame through the wait and the attempt. So one delegation
costs the store one write per task, one read of it, and one write of the result.

This matters more than a stale docstring because the store is how delegation satisfies the one hard
rule: a subagent is meant to be a stateless function over it, so a restart or a model swap
mid-delegation should lose nothing. Nothing resumes a delegation, and it is the missing reader
rather than the store that makes that so.

**What closed it: repairing the documentation, because the resume path is not a slice.** Nothing
resumes a turn at all. `handle_turn` holds the conversation in its own frame, the overlay's
`Converse` stream dies with the process, and a restarted brain has no record that a turn was in
flight, so a subtask result read back out of Redis would have nowhere to go.
[R-023](023-converse-reconnect-first-event.md) and [R-112](112-resume-crashed-handoff.md) already
cover that half, and both wait on request identity, which the brain does not define anywhere. The
resume path is filed as
[R-621](621-a-delegating-turn-cannot-be-resumed-from-the-store.md), which also records the two
things it needs and does not have: a turn's record of the ids it spawned, and a record lifetime
decided for a read taken after the queue rather than before it.

## History

- 2026-09-08: opened by the close of [R-614](614-a-refused-spawn-reaches-no-log-line.md), recorded
  in [ADR-0012](../../adr/ADR-0012-resource-governance.md) decision 16, which traced every read
  path either key has while settling whether the record outlives its own admission wait.
- 2026-09-09: claims checked against the tree and all of them stand. `get_result` still has no
  production call site, `get_task` still has the one in `SubagentRunner.run` taken before `admit`,
  the spawn tool still aggregates the list `asyncio.gather` returns, and `_TASK_TTL_SECONDS` is
  still 3600. The entry undercounted where the missing read is written down: three comments in the
  core suite say it as well as the port docstring.
- 2026-09-10: done, as the documentation repair. The port docstring in
  [ports_stores.py](../../../brain/packages/core/src/cortex_core/ports_stores.py), the
  `SubagentResult` docstring in
  [subagents.py](../../../brain/packages/core/src/cortex_core/subagents.py), the two comments in
  [test_runner.py](../../../brain/packages/core/tests/test_runner.py) and the one in
  [test_subagent_bounds.py](../../../brain/packages/core/tests/test_subagent_bounds.py) now say the
  result is persisted as well as returned. [brain-core.md](../../modules/brain-core.md) states
  which of the two reads has a caller, and
  [ADR-0010](../../adr/ADR-0010-subagents.md) decision 5 states that nothing reads a result back.
  Opened [R-621](621-a-delegating-turn-cannot-be-resumed-from-the-store.md).
