# A delegating turn cannot be resumed from the store

**Status:** open, dead until a consumer
**Area:** resource-governance
**Origin:** [ADR-0010](../../adr/ADR-0010-subagents.md)
**Verified:** 2026-09-10
**Trigger:** a turn that survives an orchestrator restart, which the seam's `Converse` reconnect entry and the request-identity design the crashed-handoff resume entry waits on would together give it. Until one exists there is nothing to hand a stored result back to.

Opened 2026-09-10 by the close of
[R-615](615-nothing-reads-a-subagent-result-back-from-the-store.md), which repaired four sentences
describing this read as though it existed and left the read itself unbuilt.

The store already holds everything a delegation would need to be finished a second time.
`SpawnSubagentsTool.invoke` writes one `SubagentTask` per instructions entry under
`cortex:task:{id}`, and `SubagentRunner._persist` writes the `SubagentResult` under
`cortex:task:{id}:result`, both at the 3600 s TTL `RedisTaskStore` sets. Neither is read back after
the run: `run` takes the task once, before it admits, and carries it in the coroutine's own frame
through the wait and the attempt, and the tool formats the list `asyncio.gather` returns. An
orchestrator that restarts mid-delegation therefore loses the turn, and the results of every
subtask that had already finished sit in Redis until they expire.

Reading them back is the smaller half of a resume. The larger half is that nothing resumes a turn
at all: `handle_turn` holds the conversation in its own frame, the overlay's `Converse` stream dies
with the process, and a restarted brain has no record that a turn was in flight.
[R-023](023-converse-reconnect-first-event.md) and
[R-112](112-resume-crashed-handoff.md) carry that half between them, and both wait on request
identity, which the brain spells nowhere.

**What would close it.** A resumable turn first, then the read. A delegating turn that came back
would look up each subtask id it had spawned, take the result the store already holds for any that
finished, and spawn only the rest, which is one `get_result` per id and a spawn tool that accepts
the ids it is resuming. That gives the result half of the `TaskStore` its first production reader
and makes the port's own promise, that a subagent is a stateless function over the store, something
a run exercises rather than something a contract test does.

Two things it needs do not exist. A turn keeps no record of which task ids it spawned, that list
living in the coroutine's frame beside everything else the restart takes. And the record lifetime
would have to be re-decided: 3600 s is deliberately shorter than the 7200 s a spawn may queue for,
which the [ADR-0012](../../adr/ADR-0012-resource-governance.md) record-lifetime addendum argues is
harmless because the only read either key has is taken before the queue starts. A resume path is a
second read taken arbitrarily later, and it would be the first read that ordering has to cover.

## Trail

- 2026-09-10: opened by the close of
  [R-615](615-nothing-reads-a-subagent-result-back-from-the-store.md), which repaired the port
  docstring, the `SubagentResult` docstring, the core module contract and three test comments that
  each described the cortex reading a result out of the store, and recorded the repair in the
  [ADR-0010](../../adr/ADR-0010-subagents.md) addendum on decision 5's last clause.
