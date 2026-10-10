# A subtask cut by Stop leaves no record

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)
**Verified:** 2026-10-10

On the Linux shell on 2026-10-10 a person pressed Stop 6.2 s into a three-item delegated batch
([readings](../../readings/delegation-overlay.md#stop-during-a-delegated-run-then-a-second-turn-at-once)).
The subagent requests were cancelled and the next turn ran cleanly. But the two cut subtasks kept a
task record with no result, and the brain wrote no audit line for the `spawn_subagents` call and no
log line at all. `ToolAuditSink` promises that every dispatched call is written, success or failure
([brain-core-tools.md](../../modules/brain-core-tools.md)), and `ToolDispatcher.dispatch` in
`cortex_core/dispatch.py` audits only after `invoke` returns, so a `CancelledError` from the turn's
cancel skips the record for any tool, not only the spawn.

Reproduction: the stack with the `subagents` override, a question asking for three paragraphs from
subagents in parallel, Stop a few seconds after the first `llama-subagent` request in the brain log,
then `redis-cli GET cortex:task:<id>:result` for each task of that turn and the audit lines.

## What to do

Audit a cancelled call before the cancellation goes on (a result naming the cancel, then re-raise),
and decide whether the runner persists an `ok=False` result for a cut subtask. Check that an audit
write under cancellation cannot itself hang a Stop.

## History

- 2026-10-10: filed from the delegation flows on the Linux shell.
