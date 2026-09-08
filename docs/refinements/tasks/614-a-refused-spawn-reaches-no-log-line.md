# A refused spawn reaches no log line

**Status:** landed 2026-09-08
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

`SubagentRunner` degrades every `SubagentAdmissionError` to an `ok=False` `SubagentResult`, which is
what keeps one refused spawn from failing the whole turn, and `_failed` writes that result and logs
nothing. The spawn tool logs nothing either, and the aggregate it returns is not an error result, so
the tool audit records `result_chars` and never the text. A spawn refused because the charge exceeds
the whole budget, because the pool is draining for a model handoff, or because the queue outlasted
`CORTEX_SUBAGENTS_ADMISSION_WAIT_S` therefore leaves the operator nothing to read.

Three backlog entries are triggered by exactly that event and so name something nobody can observe:
this entry's origin pair [R-195](195-queue-depth-bound.md) and
[R-430](430-the-bounds-are-sized-on-an-idle-box.md), and
[R-429](429-nothing-counts-how-often-the-cpu-re-run-fires.md). The two places the refusal does reach
are the cortex's own reply, which nothing keeps, and the persisted result under
`cortex:task:{id}:result`, which `RedisTaskStore` writes at a TTL of 3600 s. The shipped wait bound
is 7200 s, so the record of a spawn refused at that bound expires an hour after it is written and
the operator would have to be looking already.

**What closed it.** One `_logger.warning` where `SubagentRunner` degrades the error, in the
`except` rather than in `_failed`, since the two refusals `_failed` also writes ("task not found"
and an unknown model) are faults in the call rather than in the deployment's capacity. It carries
`task_id`, the resolved roster entry's `model` and the scheduler's own `reason`, so which of the
three refusals this was is on the line. The model named is the resolved entry rather than the
requested one, which is `""` whenever the cortex let the roster choose. The delegation runbook shows
the rendered line beside the wait bound's own paragraph, which puts it under `samplecheck.py`.

The TTL sentence above was re-derived rather than taken on trust, and the alarming reading of it is
wrong: `run` reads the task once, before `admit`, and carries it through the wait in the coroutine's
own frame, so the task key's only read is taken before the queue starts. Nothing else reads a task
back, and nothing at all reads a result back, so there is no rehydrate path for the shorter TTL to
break and the two numbers are deliberately not held together. What the shorter TTL does cost is the
audit pair, a result key with no task key beside it, which is the cost this entry's log line
removes. The absent reader is filed as
[R-615](615-nothing-reads-a-subagent-result-back-from-the-store.md).

## Trail

- 2026-09-08: opened by the trigger sweep on [R-195](195-queue-depth-bound.md), which went looking
  for where a wait-bound refusal would be seen and found that it is seen nowhere.
- 2026-09-08: landed. The warning is in `SubagentRunner.run`, the rendered line is in
  [subagents-cpu.md](../../runbooks/subagents-cpu.md), the contract is in
  [brain-core.md](../../modules/brain-core.md), and the reasoning, the mutation table and the
  settled record-lifetime question are in the
  [ADR-0012](../../adr/ADR-0012-resource-governance.md) refusal-log addendum. Opened
  [R-615](615-nothing-reads-a-subagent-result-back-from-the-store.md).
