# A refused spawn reaches no log line

**Status:** open, actionable
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

**What would close it.** One `_logger.warning` where `SubagentRunner` degrades the error, carrying
the task id, the requested model and the reason, which is the same shape as the re-run warning
already beside it. That is enough for the three triggers above to be read off the brain's log
rather than off a Redis key with a shorter life than the bound it records. The gates it must satisfy
are the ordinary ones for a new call site: a logger name owned by one module, a message spelled
once, and a documented sample only if a runbook shows the line.

## Trail

- 2026-09-08: opened by the trigger sweep on [R-195](195-queue-depth-bound.md), which went looking
  for where a wait-bound refusal would be seen and found that it is seen nowhere.
