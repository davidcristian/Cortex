# ADR-0010: Subagents as delegation via a native tool, over a task store + CPU budget

**Status:** Accepted (2026-09-10)

## Context

The cortex needs helpers: it delegates narrow tasks to small (2-4B) **subagents** and reads their
results. The cortex *itself* decides to delegate and **picks how many subagents and which size**.
That is a mid-turn judgment made by the model, which a routing decision taken once before inference
cannot express. And per the one hard rule, a subagent must be a **stateless function over the
store**: its task and result live outside any model process, so a swap loses nothing.

Three existing interfaces frame this. The cortex acts through **native function-calling**
([ADR-0009](ADR-0009-tools-mcp.md)): the model emits tool calls, the `TurnEngine` dispatches them
through the audited `ToolDispatcher`, feeds results back, and infers again in a limited loop, which
is the form a "spawn helpers and read their results" step needs. Body OS actions are **internal
tools dispatched through the core's `ToolRegistry`** ([ADR-0001](ADR-0001-architecture.md)), so a
built-in (non-MCP) tool interface was coming regardless, and delegation is its first user. And the
`ModelManager` ([ADR-0007](ADR-0007-model-manager-inference.md)) holds the GPU as an exclusive
lease, which is the wrong form for a pool of *concurrent* workers: that is a counting budget, not a
lock.

## Decision

### The tool and the loop

1. **Delegation is a native `spawn_subagents` tool, dispatched through the audited tool loop.**
   One call, `spawn_subagents(instructions)`, spawns one subagent per item, and the batch runs
   concurrently under the `SubagentScheduler` (`asyncio.gather` over the runners). The batch form
   is what makes the concurrency budget matter: the tool loop dispatches a step's calls one after
   another, so one subagent per call would never exercise it. The model may still emit several
   `spawn_subagents` calls in one step, and each runs its batch. An item is a bare instruction or
   an object naming a model from the list and its working material
   ([ADR-0018](ADR-0018-heterogeneous-subagents.md) decision 1). Bad arguments return an `is_error`
   `ToolResult` the model can correct, never an exception. Results return as `ToolResult`s fed back
   into the same loop, so the cortex reads them and continues its answer.

2. **A `CompositeToolRegistry` in the pure core merges built-in tools with the MCP registry, behind
   the unchanged `ToolRegistry` port** (`composite.py`). A built-in is a pure-core handler, not an
   MCP call. The composite advertises the union and routes `invoke` by name. Built-ins take
   precedence: a remote tool sharing a built-in's name is neither advertised nor invoked, and two
   built-ins with one name are a construction error. The body's OS actions and the schedule
   operations register here the same way.

3. **The limited infer-and-tool loop is one shared pure runner** (`stream_tool_loop` in
   `tool_loop.py`). The cortex turn and a subagent run the same thing: stream from a model with
   tools available; on tool calls, dispatch (audited) and feed results back; repeat until a final
   text answer or `MAX_TOOL_STEPS`. The `TurnEngine` and the `SubagentRunner` both call it, so the
   loop's behaviour and its tests are shared.

4. **Subagents are tools-enabled but delegation-free, so the tree is one level deep.** A subagent
   runs the shared loop on the subagent model with the MCP tool subset, every call through its own
   audited `ToolDispatcher`. It does **not** receive `spawn_subagents`, so fan-out stops at one
   level. It is never given a tool that needs confirmation or one that sends anything outward
   either: `build_subagent_tools` wraps the registry in `ConfirmFreeToolRegistry`
   ([ADR-0013](ADR-0013-untrusted-content.md) decision 9). A tools-enabled subagent always runs on
   the injection-resistant default entry ([ADR-0018](ADR-0018-heterogeneous-subagents.md) decision
   3).

### State and admission

5. **A subagent is a stateless function over a `TaskStore` (Redis hot state).** The spawn tool
   writes one `SubagentTask` per item, the runner loads it, works, and persists a `SubagentResult`
   (task id, output, ok, detail) as well as returning it. Task state is hot and in flight, so it
   lives in Redis (mirroring `SessionStore`), never in a model process. The tool builds its
   aggregate from the results `gather` returns; `TaskStore.get_result` reads one back by id and has
   no production caller, so the stored result serves a test and an operator with `redis-cli`. The
   reader it was written for is a delegating turn resumed after an orchestrator restart, which
   would find its subtasks' results and finish rather than spawn again; that is
   [task 621](../refinements/tasks/621-a-delegating-turn-cannot-be-resumed-from-the-store.md).
   Durable value moves into memory at turn end through the existing path, and the store itself is
   ephemeral. The `TaskStore` port, fake and contract suite exercise this without Redis.

6. **Admission is a dedicated `SubagentScheduler` port, separate from the `ModelManager`.** The GPU
   lease is mutual exclusion; the subagent pool is limited concurrency, where `admit()` yields a
   slot and several workers run at once. One port models one contract, so they stay separate, and
   the three resources (GPU lease, VRAM ledger, CPU and RAM budget) compose at the runner. The
   implementation in use is `ResourceBudgetScheduler`, a two-dimensional CPU and RAM soft budget
   ([ADR-0012](ADR-0012-resource-governance.md) decision 4). Over budget, a spawn **waits**, which
   cannot deadlock because a one-level tree guarantees no spawn waits on another spawn, and the
   wait is time-limited (ADR-0012 decision 11). A model handoff empties the pool through the
   scheduler's `drain`, composed at the orchestrator (ADR-0012 decision 10), never by merging the
   two ports.

7. **Subagent inference reuses the `InferenceBackend` port, and placement is GPU-first.** A
   subagent completion is one stateless streamed completion, which is what `InferenceBackend` is.
   The placer fit-tests each spawn against the VRAM headroom and places the whole subagent on the
   GPU or on a CPU `llama-server`, never split between them
   ([ADR-0012](ADR-0012-resource-governance.md) decisions 1 to 6); the dedicated CPU server is the
   overflow path. Every subagent server runs with reasoning disabled, because narrow subtasks do
   not need it and an unlimited trace on the CPU costs minutes per call
   ([ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md) decision 8, checked by
   [ADR-0043](ADR-0043-subagent-server-flags.md)). CI uses a scripted fake backend, as the cortex
   path does.

8. **Opt-in, mirroring memory and tools.** `CORTEX_SUBAGENTS_BACKEND` is `none` by default or
   `llamacpp`; with it off the cortex's tool set has no `spawn_subagents` and the turn path is
   unchanged. CI and the no-GPU dev loop stay subagent-free.

### The batch cap

9. **One call's batch is capped at `MAX_SPAWN_BATCH = 8`** (`spawn_spec.py`). The turn's dispatch
   pool ([ADR-0009](ADR-0009-tools-mcp.md) decision 11) limits what a batch may reach, not how much
   work it queues: a subagent that calls no tools spends nothing from that pool while still costing
   an admission, a placement and a model run, and admission queues rather than refuses, so an array
   of fifty was fifty inferences the turn waited through. An oversized batch is **refused**, never
   truncated, because a silently shortened batch returns an aggregate that reads as complete, while
   an `is_error` result is something the model corrects by delegating in batches that fit. The
   check runs ahead of item parsing, so an oversized array is refused before a task is stored or a
   subagent placed. The cap is advertised twice, as the array's `maxItems` (a limit a constrained
   decoder enforces) and in the prose descriptions, so the runtime check is the last line of
   defence.

10. **The cap is per call, not a turn-wide pool.** A spawn costs a quarter of the dispatch pool by
    default (`DEFAULT_SPAWN_COST`), so a turn affords four batches and its maximum is four times
    this cap: two deliberate factors, where the dispatch budget replaced a product with an
    unlimited factor. A user who reprices `spawn_subagents` through `CORTEX_TOOLS_COSTS` moves one
    factor knowingly. A turn-wide pool would end delegation for the rest of the turn at the first
    oversized batch, where a per-call refusal is correctable. A refused batch still pays its spawn
    price, because the loop charges before it dispatches, so retries are limited to four.

11. **The cap is a code constant, not an environment setting.** The CPU and memory budgets tune what
    one host can run at once, a deployment fact; how many subtasks one call may ask for is a policy
    the composition root does not vary. Eight sits above plausible delegation (two to five parallel
    subtasks) and far below fan-out spam. A per-host setting would be two settings: the admission
    wait is derived over a full batch of eight
    ([ADR-0047](ADR-0047-delegated-run-bound-ordering.md) decisions 4 and 5), and a new maximum
    without a retuned wait leaves that default describing a number it no longer derives from. When a
    second deployment needs one, it is a keyword-only parameter defaulting to the constant, threaded
    through `build_spawn_spec` and `SpawnSubagentsTool.__init__`, which breaks no existing
    construction.

12. **No cost-aware batch cap.** A cap in placements equals the cap in items, because the tool
    builds one task per item and the runner places each once (its one CPU re-run releases the first
    reservation and reuses the admission, [ADR-0012](ADR-0012-resource-governance.md) decision 12).
    A cap in estimated VRAM limits what the placer already limits, since it spills to the CPU
    rather than overspend the card. And a summed-cost cap is neither a structural limit a decoder
    can apply nor one the prose can state, and it would have to walk the array that the size check
    refuses unwalked. What would reopen it is a model in the list whose `cpus` differs from the
    default's, and the answer there is a per-model maximum.

### Progress while a batch runs

13. **Subagent progress is sent through a `ProgressSink` passed per call on the `TurnStamp`.**
    While a spawn runs, the turn's generator is suspended inside the dispatch and cannot yield an
    event, and `SpawnSubagentsTool` is built once and shared by every stream, so it cannot hold one
    stream's channel. The engine stamps its stream's sink onto each dispatch beside the budget; the
    tool reads `call.stamp.progress` and hands it to each `SubagentRunner.run`, so the shared tool
    keeps no per-stream field that could leak across turns. A caller with no stream (the schedule
    ticker) passes `None`.

14. **What it shows needs no guardrail pass.** The tool holds one wait for the batch on the sink,
    `queued` while any subtask has not been admitted and `delegating` after, with counts such as
    "1 subtask running, 1 waiting for room to run" (ADR-0069 decision 9), and the runner maps
    each subagent's audited `ToolStep` onto a `ToolActivity`. Every field is registry-authored or
    a brain-authored count,
    never the model's call or untrusted content, so a tainted subagent's progress contains nothing
    injectable, the same argument the cortex's own `ToolActivity` makes. The wording claims no
    parallelism: spawns on one model do not deliver it (ADR-0018 decision 8).

15. **The gRPC adapter is best-effort and credit-balanced.** `RpcProgressSink` puts onto the
    stream's output queue only when a buffer credit is free and otherwise drops the event, so a
    slow overlay costs cosmetic progress and never stalls a subagent, and the buffer limit stays
    exact. The order on the queue is natural because the turn task puts nothing while suspended. No
    proto change was needed: the overlay already renders `ToolActivity` and `StatusUpdate`.

## Consequences

- **Fan-out is limited four ways:** one level deep, the per-call batch cap, the scheduler's budget,
  and `MAX_TOOL_STEPS` on every loop, with the turn's dispatch pool limiting what the batches
  reach. The audit log makes runaway delegation visible.
- **The run's own limits nest.** A delegated run stands between a stream stall timeout, a run
  deadline and the admission wait, each strictly above the last and refused at startup when not
  ([ADR-0047](ADR-0047-delegated-run-bound-ordering.md)).
- **Small models on the CPU are slow.** Delegation is synchronous within the cortex turn, and the
  progress channel is what the user sees meanwhile. The advertised timing wording is ADR-0018
  decision 8.
- **Small-model tool calling is validated on real models, not in CI.** A malformed or failed
  subagent tool call becomes an `is_error` `ToolResult` the subagent loop can recover from, the
  same contract the cortex loop has.
- **Validation.** The delegation machinery was proven end to end against a real CPU `llama-server`
  (concurrent subagents, the batch aggregate, `is_error=False`), and a resident cortex deciding to
  call `spawn_subagents` was confirmed on the host on 2026-07-01; `test_subagent_live.py`
  reproduces the first, and the runbook records both.
- **Nothing reads a stored result back** until a resume path exists (decision 5); how long the
  record lives against the admission wait is ADR-0012 decision 16.

## Alternatives rejected

- **A route-time `Delegator` keyed off a narrow-task check.** It fixes the tier once, before
  inference, and cannot express "the cortex picks how many and how big".
- **Merging admission into the `ModelManager`.** It would mix an exclusive lease with a counting
  budget in one port and break the manager's single-GPU invariant.
- **Truncating an oversized batch**, a **turn-wide batch pool**, an **environment setting for the
  cap** and a **cost-aware cap** (decisions 9 to 12).

## Related

- Module contracts: [brain-core.md](../modules/brain-core.md),
  [brain-orchestrator.md](../modules/brain-orchestrator.md).
- Runbook: [subagents-cpu.md](../runbooks/subagents-cpu.md).
- Readings: [delegated run holds](../readings/delegated-run-holds.md),
  [subagent budget](../readings/subagent-budget.md).
- [ADR-0012](ADR-0012-resource-governance.md) (placement, budget, drain),
  [ADR-0017](ADR-0017-subagent-model-safety.md) and
  [ADR-0018](ADR-0018-heterogeneous-subagents.md) (the model list and its safety rule),
  [ADR-0047](ADR-0047-delegated-run-bound-ordering.md) (ordering the limits),
  [ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md) (reasoning off on subagent servers).
