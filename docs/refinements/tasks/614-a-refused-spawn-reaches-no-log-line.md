# A refused spawn reaches no log line

**Status:** done 2026-09-08
**Area:** resource-governance
**Origin:** [ADR-0012](../../adr/ADR-0012-resource-governance.md)

`SubagentRunner` turns every `SubagentAdmissionError` into an `ok=False` `SubagentResult`, which is
what keeps one refused spawn from failing the whole turn, and `_failed` writes that result without
logging. The spawn tool logs nothing either, and the aggregate it returns is not an error result, so
the tool audit records `result_chars` and never the text. A spawn refused because the charge exceeds
the whole budget, because the pool is draining for a model handoff, or because the queue outlasted
`CORTEX_SUBAGENTS_ADMISSION_WAIT_S` left the operator nothing to read.

Three backlog entries are triggered by exactly that event and so named something nobody could
observe: [R-195](195-queue-depth-bound.md),
[R-430](430-the-bounds-are-sized-on-an-idle-box.md) and
[R-429](429-nothing-counts-how-often-the-cpu-re-run-fires.md). The refusal reached two places only,
the cortex's own reply, which nothing keeps, and the persisted result under
`cortex:task:{id}:result`, which `RedisTaskStore` writes at a TTL of 3600 s. The shipped wait bound
is 7200 s, so a spawn refused at that bound expires an hour after it is written.

**What closed it.** One `_logger.warning` where `SubagentRunner` turns the error into a result, in
the `except` rather than in `_failed`, because the two refusals `_failed` also writes ("task not
found" and an unknown model) are faults in the call rather than in the deployment's capacity. It
includes `task_id`, the resolved roster entry's `model` and the scheduler's own `reason`, so the
line says which of the three refusals happened. The model named is the resolved entry rather than
the requested one, which is `""` whenever the cortex let the roster choose. The delegation runbook
shows the rendered line beside the wait bound's own paragraph, which puts it under `samplecheck.py`.

The TTL sentence above was checked rather than taken on trust, and the alarming reading of it is
wrong: `run` reads the task once, before `admit`, and keeps it through the wait in the coroutine's
own frame, so the task key is only read before the queue starts. Nothing else reads a task back,
and nothing reads a result back, so there is no resume path for the shorter TTL to break. What it
does cost is a result key with no task key beside it in the audit. The missing reader is filed as
[R-615](615-nothing-reads-a-subagent-result-back-from-the-store.md).

## History

- 2026-09-08: opened by the trigger review on [R-195](195-queue-depth-bound.md), which looked for
  where a wait-bound refusal would be seen and found that it is seen nowhere.
- 2026-09-08: done. The warning is in `SubagentRunner.run`, the rendered line is in
  [subagents-cpu.md](../../runbooks/subagents-cpu.md), the contract is in
  [brain-core.md](../../modules/brain-core.md), and the reasoning, the mutation table and the
  settled record-lifetime question are in
  [ADR-0012](../../adr/ADR-0012-resource-governance.md) decision 9. Opened
  [R-615](615-nothing-reads-a-subagent-result-back-from-the-store.md).
