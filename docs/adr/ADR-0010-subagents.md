# ADR-0010: Subagents as delegation via a native tool, over a task store + CPU budget

- **Status:** Accepted (Slice 7)
- **Date:** 2026-06-29

## Context

Slice 7 gives the cortex helpers: it delegates narrow tasks to small (2-4B) **subagents**
that run on **CPU** (the GPU's 14 GB soft cap is spent on the resident cortex, per the ADR-0004
addendum), and consumes their results. Per the founding arc the cortex *itself* decides to
delegate and **picks how many subagents and which size**. That is a dynamic, mid-turn judgment, not
a routing decision made once before inference. And per the one hard rule, a subagent must be
a **stateless function over the store**: its task and result live outside any model process,
so a swap loses nothing.

Three existing seams frame this. The cortex acts through **native function-calling**
(ADR-0009): the model emits tool calls, the `TurnEngine` dispatches them through the audited
`ToolDispatcher`, feeds results back, and re-infers in a bounded loop that is exactly the shape
a "spawn helpers and read their results" step needs. ADR-0001 open-question 2 already commits
body OS-actions (Slices 9-10) to being **internal tools dispatched via the core's
`ToolRegistry`**. So a *built-in* (non-MCP) tool seam is coming regardless; delegation is its
first user. And the `ModelManager` (ADR-0007) owns the single GPU as an exclusive lease. That is the
wrong shape for a CPU pool of *concurrent* workers, which is a counting budget, not a lock.

## Decision

1. **Delegation is a native `spawn_subagent` tool, dispatched through the audited tool loop.**
   The cortex delegates by *calling a tool* mid-turn, by its own judgment, one or more calls
   per step (the loop already collects several calls per step), picking count and size. Results
   return as `ToolResult`s fed back into the same loop, so the cortex reads them and continues
   its answer. This reuses native function-calling and the audit trail wholesale; the rejected
   alternative (a route-time `Delegator` keyed off `is_narrow_delegable`) fixes the tier once,
   before inference, and cannot express "the cortex picks how many and how big."

2. **A `CompositeToolRegistry` in the pure core merges built-in tools with the MCP registry,
   behind the unchanged `ToolRegistry` port.** `spawn_subagent` is the first **built-in** tool:
   a pure-core handler, not an MCP call. The composite advertises the union of built-in specs
   and the wrapped registry's specs, and routes `invoke` by name (built-ins take precedence; a
   built-in name shadowing an MCP tool is a wiring error surfaced at construction). The tool
   loop is untouched. It just sees more tools. This is the internal-tool seam ADR-0001 Q2
   predicted; Slices 9-10 register body actions the same way.

3. **The bounded infer↔tool loop is extracted from `TurnEngine` into a shared pure runner.**
   Both the cortex turn and a subagent run the same thing: *stream from a model with tools
   available; on tool calls, dispatch (audited) and feed results back; repeat until a final
   text answer or `MAX_TOOL_STEPS`.* That loop, inlined in `handle_turn` today, moves to a
   reusable core helper the `TurnEngine` and the `SubagentRunner` both call, with no duplication,
   both files stay ≤300 lines, and cortex behavior is preserved (proven by the existing turn
   tests).

4. **Subagents are tools-enabled but delegation-free. The tree is depth-1.** A subagent runs
   the shared loop on the **subagent** model with the *non-delegation* tool subset (filesystem,
   email, each read-only in v1), so it can do real work; every subagent tool call flows through the
   **same audited `ToolDispatcher`**. It does **not** receive `spawn_subagent`, so a subagent
   cannot spawn subagents: fan-out is bounded to one level (cortex → subagents), no recursion.

5. **A subagent is a stateless function over a `TaskStore` (Redis hot state).** `spawn_subagent`
   writes a `SubagentTask` (id, instruction, context, tool-subset) to the store, the runner
   loads it, works, and persists a `SubagentResult` (task id, output, ok, detail) back, and the
   cortex reads the result from the store. Task state is hot and in-flight, so it lives in Redis
   (mirroring `SessionStore`), never in a model process (the hard rule, proven for task state).
   Durable value rolls into memory at cortex turn end via the existing path; the `TaskStore`
   itself is ephemeral. A new `TaskStore` port + fake + contract test prove it without Redis.

6. **CPU admission is a dedicated `SubagentScheduler` port (not the `ModelManager`).** The two
   compute resources have different semantics: the GPU is *mutual exclusion* (`ModelManager`
   owns one resident model, `acquire()` is an exclusive lease); the CPU subagent pool is
   *bounded concurrency* (`SubagentScheduler.admit()` yields a slot, N workers run at once). A
   port models one contract, so they stay separate, keeping the `ModelManager`'s "owns the
   single GPU" invariant clean and each fake trivial. `admit()` is an async context manager
   capped at `CORTEX_SUBAGENTS_MAX_CONCURRENCY`; over-cap spawns **wait** (queue), which is safe
   because depth-1 guarantees no spawn waits on another spawn. Hard RAM-ceiling *rejection*
   (fail-fast rather than queue) is a noted refinement. A pure `asyncio.Semaphore` implementation
   lives in the core, fully covered without a GPU or a real workload. This **refines** the
   ROADMAP's "the ModelManager admits or rejects each spawn"; the Slice 11 swap (which quiesces
   subagents) composes both ports at the orchestrator via a scheduler drain, not by merging them.

7. **Subagent inference reuses the `InferenceBackend` port, pointed at a CPU `llama-server`.**
   A subagent completion ("one stateless streamed completion against a loaded model") is exactly
   `InferenceBackend`. The subagent model (id `subagent`, ADR-0004) runs on its own CPU
   `llama-server` sidecar (ADR-0005: one process per model), reached at a second endpoint; the
   composition root selects the per-tier backend. There is **no GPU lease** for subagents, since the
   GPU stays the cortex's and `SubagentScheduler` gates the CPU. CI uses a scripted fake backend,
   exactly as the cortex path does.

8. **Opt-in, mirroring memory and tools.** `CORTEX_SUBAGENTS_BACKEND` (`none` default, a backend
   enables); with it off, the cortex's tool set has no `spawn_subagent` and the turn path is
   byte-for-byte the Slice 6 behavior. CI and the no-GPU dev loop stay subagent-free.

## Consequences

Increments (each small, green, documented), mirroring Slices 5-6:

1. **The pure subagent core** covers the `SubagentTask`/`SubagentResult` values, the `TaskStore` +
   `SubagentScheduler` ports with fakes and contract tests, the shared infer↔tool loop extracted
   from `TurnEngine`, and the `SubagentRunner` use-case (admit → load task → run the loop on the
   subagent model → persist result), fully covered in the core, no I/O.
2. **The native `spawn_subagent` tool + `CompositeToolRegistry`** are the built-in tool whose
   handler runs one or more `SubagentRunner`s concurrently under the scheduler and returns their
   results; the composite registry merging built-in + MCP tools behind the port; wired into the
   turn via `TurnCapabilities`. Subagents get the delegation-free tool subset (depth-1). Over the
   fakes, end to end.
3. **Adapters (CI half)** are the Redis `TaskStore` adapter (behind a fake `Database`, 100% without
   Redis, the accepted MockTransport pattern), the concurrency-capped scheduler config, opt-in
   `run_from_env` wiring (`CORTEX_SUBAGENTS_*`), and `docker-compose.subagents.yml` (a CPU
   `llama-server` sidecar + the subagent model bind mount). Green under `just check`, no GPU/Redis.
4. **Host half** is a real CPU `llama-server` running a small subagent model (a Qwen3.5-2B Q4_K_M
   candidate, ADR-0004), end-to-end delegation validated on the host (cortex spawns, subagents
   work with tools, results consumed), a runbook (`docs/runbooks/subagents-cpu.md`), and the
   ADR-0004 subagent-pick addendum with the measured CPU footprint/latency.

Config gains, at the composition root only: `CORTEX_SUBAGENTS_BACKEND`, the subagent model
endpoint/id, and `CORTEX_SUBAGENTS_MAX_CONCURRENCY`.

## Risks

- **Fan-out / recursion explosion.** Bounded three ways: depth-1 (subagents lack `spawn_subagent`),
  the `SubagentScheduler` concurrency cap, and `MAX_TOOL_STEPS` on every loop. The audit trail
  makes runaway delegation visible.
- **CPU subagent latency.** Small models on CPU are slow; mitigated by bounded concurrency and
  keeping subagents narrow. Progress is reported to the overlay via the `Converse` status stream
  (a later refinement); v1 delegation is synchronous within the cortex turn.
- **Tiny-model tool-calling reliability.** 2-4B tool-calling under llama.cpp + `--jinja` is
  validated on the host, not CI. A malformed or failed subagent tool call becomes an `is_error`
  `ToolResult` the subagent loop can recover from, the same contract the cortex loop already has.
- **Touching the cortex tool loop during extraction.** The shared runner must preserve cortex
  behavior exactly; the existing turn tests (including the tool-loop cases) are the guard, run
  before and after the extraction.
- **Swap coupling (Slice 11).** A brain handoff quiesces subagents. The `SubagentScheduler` exposes
  a drain the orchestrator calls during a swap; the two admission ports are composed there, never
  merged, so this ADR's separation holds.

## Addendum (2026-06-29): in increment 2 the tool is `spawn_subagents` (a concurrent batch)

The built-in tool is **`spawn_subagents(instructions: string[])`**. One call spawns *N* subagents
that run **concurrently** under the `SubagentScheduler`, not one subagent per call dispatched
sequentially by the tool loop. The batch form is what makes the concurrency budget meaningful:
the tool loop dispatches a step's tool calls sequentially, so per-call spawning would never exercise
the CPU cap. The model still *may* emit several `spawn_subagents` calls in one step (decision 1
holds); each runs its batch. v1 folds any per-subtask context into the instruction string
(`SubagentTask.context` stays `""` from this tool). A richer object schema (`{instruction,
context}[]`) is a later refinement behind the same tool. Bad arguments return an `is_error`
`ToolResult` the model can correct, not an exception. The `CompositeToolRegistry` gives built-ins
precedence over remote (MCP) tools of the same name. The shadowed remote tool is neither advertised
nor invoked, and duplicate built-in names are a construction error.

## Addendum (2026-06-29): increment 4 validated the machinery on a real CPU model

The delegation path was validated end to end against a real CPU `llama-server`. Because a plain
WSL distro cannot see the user's `D:\Software\AI\Models` drive (the Windows bind resolves only
host-side, the same constraint as the Slice 4 GPU run), the validation used a **stand-in** small
model in a WSL-local dir: **Qwen2.5-1.5B-Instruct Q4_K_M** on `ghcr.io/ggml-org/llama.cpp:server`
(`-ngl 0 --jinja --parallel 2`). Invoking `spawn_subagents` directly (as the cortex would) with
three instructions ran three subagents **concurrently** under the `ConcurrencyScheduler` and folded
their results in order ("capital of France" → *Paris*, "17 + 25" → *42*, and a one-word reply), with
`is_error=False`, each body non-empty. This exercises the real `LlamaCppBackend` (CPU),
`SubagentRunner`, the concurrency budget, and the batch aggregation. The integration test
(`test_subagent_live.py`, host-only) reproduces it; the runbook is
[docs/runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md).

Two things remain the host-only half (they need the GPU cortex + the real model on `D:`):
the **cortex-driven** path (a resident gemma-4-12B *deciding* to emit `spawn_subagents`), and
**locking the final subagent pick** (the real Qwen3.5-2B) in the ADR-0004 addendum with its measured
CPU footprint/latency. The machinery under both is the same code proven above.
