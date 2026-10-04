# A delegating turn cannot be resumed from the store

**Status:** open, waiting for a consumer
**Area:** resource-governance
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)
**Verified:** 2026-10-04
**Trigger:** a request identity on the body/brain interface, meaning a request id on `UserTurn` or
`ClientEvent` in `proto/body.proto` (`grep -ni request_id proto/body.proto` has no hit), which is
what both the `Converse` reconnect entry (R-023) and the crashed-handoff resume entry (R-112) wait
on and what a turn surviving an orchestrator restart needs first. A production caller of
`TaskStore.get_result` would also fire it: `grep -rn 'get_result(' brain/packages/*/src` hits only
the port, the fake and the Redis adapter.

The store already holds everything a delegation would need to be finished a second time.
`SpawnSubagentsTool.invoke` writes one `SubagentTask` per instructions entry under
`cortex:task:{id}`, and `SubagentRunner._persist` writes the `SubagentResult` under
`cortex:task:{id}:result`, both at the 3600 s TTL `RedisTaskStore` sets. Neither is read back after
the run: `run` takes the task once, before it admits, and keeps it in the coroutine's own frame
through the wait and the attempt, and the tool formats the list `asyncio.gather` returns. An
orchestrator that restarts mid-delegation loses the turn, and the results of every subtask that had
already finished sit in Redis until they expire.

Reading them back is the smaller half of a resume. The larger half is that nothing resumes a turn at
all: `handle_turn` holds the conversation in its own frame, the overlay's `Converse` stream dies
with the process, and a restarted brain has no record that a turn was in flight.
[R-023](023-converse-reconnect-first-event.md) and [R-112](112-resume-crashed-handoff.md) cover that
half between them, and both wait on request identity, which the brain does not define anywhere.

**What would close it.** A resumable turn first, then the read. A delegating turn that came back
would look up each subtask id it had spawned, take the result the store already holds for any that
finished, and spawn only the rest: one `get_result` per id, plus a spawn tool that accepts the ids
it is resuming. Two things it needs do not exist. A turn keeps no record of which task ids it
spawned, that list living in the coroutine's frame beside everything else a restart takes. And the
record lifetime would have to be decided again: 3600 s is deliberately shorter than the 7200 s a
spawn may queue for, which [ADR-0012](../../adr/ADR-0012-resource-governance.md) decision 16
explains is harmless because the only read either key has is taken before the queue starts. A
resume path is a second read taken arbitrarily later.

**Why this is not a breach of the one hard rule.** That rule covers a model swap, and no swap
runs while a delegation is in flight. `EscalatingEngine.handle_turn` starts the handoff only after
the cortex phase ends, so the escalating turn's own `spawn_subagents` calls have all returned. A
subtask of another turn holds the swap back: `SwapConductor._drain` waits up to
`CORTEX_SWAP_DRAIN_TIMEOUT_S` (60 s by default) for the in-flight count to reach zero, and on a
timeout fails the handoff with nothing evicted; a spawn still queued is refused with
`POOL_DRAINING_MSG` and comes back as a failed result. A co-resident handoff stops no tier a
subtask can reach. The batch's frame lives in the orchestrator process, which a swap does not
restart. The one reachable path that loses a delegation is that process ending mid-batch (a crash,
an out-of-memory kill, a restart of the brain service), and it loses the whole turn, which is the
half R-023 and R-112 own. This entry alone is therefore a read nothing can reach, and its whole
size is a port change across both languages: request identity on the proto, a turn record of the
task ids it spawned, and a new decision on the 3600 s record life.

## History

- 2026-09-10: opened by the close of
  [R-615](615-nothing-reads-a-subagent-result-back-from-the-store.md), which repaired the port
  docstring, the `SubagentResult` docstring, the core module contract and three test comments that
  each described the cortex reading a result out of the store, and brought
  [ADR-0010](../../adr/ADR-0010-subagents.md) decision 5 in line with the code.
- 2026-09-17: checked again, not fired, and the trigger restated as two greps. Both entries the old
  trigger leaned on are still open and neither has built request identity: R-023 was checked again
  today with its trigger moved onto `CORTEX_ESCALATION`, and R-112 still waits on the same request
  id. `SubagentRunner.run` reads `get_task` once (`runner.py:101`) and `_persist` writes the result
  (`runner.py:212`); both keys sit at `_TASK_TTL_SECONDS = 3600` in `cortex_session/tasks.py`,
  against `DEFAULT_ADMISSION_WAIT_S = 7200.0` in `scheduler.py`; and no commit since 2026-09-10 has
  changed the runner, the spawn tool, the task store or the port.
- 2026-09-24: Not fired. Both greps were run: `proto/body.proto` has no `request_id`, and
  `get_result(` appears only in the port, the fake and the Redis adapter. R-023's trigger now names
  a record of a lost turn rather than the switch alone, and neither it nor R-112 has built request
  identity. The 2026-09-17 line numbers were stale: `run` reads `get_task` at `runner.py:64` and
  `_persist` writes the result at `runner.py:142`. One commit since changed the runner and the spawn
  tool, adding the callback that reports admission; `run` still takes the task once before it
  admits, and `spawn.py:175` still gathers the results in the frame. Both TTLs are as stated.
- 2026-09-28: Not fired. Both greps give the same answer, and no commit since 2026-09-24 has
  touched `runner.py`, `spawn.py` or `cortex_session/tasks.py`; the handoff record's new refusal of
  a system message in its loop tail adds no request identity either.
- 2026-10-04: Not fired, and read against the one hard rule: it is not a breach, for the reasons
  the body now gives. Both greps still answer no; `run` reads `get_task` at `runner.py:73` before
  it admits, `_persist` writes the result at `runner.py:157`, and `spawn.py:193` gathers the batch
  in the frame. No commit since 2026-09-28 touched the runner, the spawn tool or the task store.
