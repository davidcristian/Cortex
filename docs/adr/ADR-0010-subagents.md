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
   `run_from_env` wiring (`CORTEX_SUBAGENTS_*`), and `docker/docker-compose.subagents.yml` (a CPU
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

The delegation path was validated end to end against a real CPU `llama-server` running the
**user's actual subagent pick** (`unsloth/Qwen3.5-2B-GGUF/Qwen3.5-2B-Q4_K_M.gguf`), mounted from
`/srv/models` (the models are reachable from WSL at `/srv`; an earlier draft of this addendum
wrongly said the drive was unreachable and used a stand-in). On `ghcr.io/ggml-org/llama.cpp:server`
(`-ngl 0 --jinja --parallel 2`) the model loaded in ~14.5 s, resident RSS ~893 MiB. Invoking
`spawn_subagents` directly (as the cortex would) ran the subagents **concurrently** under the
`ConcurrencyScheduler`; with thinking disabled the model answered correctly and fast ("17 + 25" →
*42* in ~0.6 s), `is_error=False`. This exercises the real `LlamaCppBackend` (CPU), `SubagentRunner`,
the concurrency budget, and the batch aggregation. The integration test (`test_subagent_live.py`,
host-only) reproduces it; the runbook is [docs/runbooks/subagents-cpu.md](../runbooks/subagents-cpu.md).

**Finding + fix (subagents run with reasoning disabled).** Qwen3.5/3.6 are *reasoning* models:
unbounded on CPU they emit long `<think>` traces (minutes per call, so the naive run timed out), and
llama.cpp streams those into `reasoning_content`, leaving the assistant `content` (what
`LlamaCppBackend` reads) empty until reasoning finishes. Narrow subagent tasks do not need it, so
the dedicated subagent `llama-server` **disables reasoning** via `--chat-template-kwargs
'{"enable_thinking": false}'` (baked into `docker/docker-compose.subagents.yml`). This was chosen over a
per-request backend change because it needs no code, keeps the shared `InferenceBackend` untouched,
and (being a server flag) llama.cpp applies the right per-model mechanism (the kwarg is ignored by
non-reasoning templates like gemma-4-E\*, so overriding the model stays correct). Verified: with the
flag, plain requests answer directly in ~0.3-0.6 s and the live delegation test passes end to end.
(`--reasoning-budget 0` did **not** work on this build. It still produced reasoning; only
`--chat-template-kwargs` / the per-request `enable_thinking` disabled it.)

At the time of this addendum, the **cortex-driven** path (a resident gemma-4-12B *deciding* to
emit `spawn_subagents` end to end) remained the host-only half (needs the GPU); it was
closed 2026-07-01 (see the closure addendum below). The measured pick is recorded in the
[ADR-0004 addendum](ADR-0004-model-lineup.md).

## Addendum (2026-07-01): subagents are GPU-first, not CPU-only (revises decisions 6-7)

At the user's direction, subagents are **GPU-first with CPU overflow**, not CPU-only. Decisions
6-7 kept the `SubagentScheduler` (CPU concurrency) cleanly separate from the `ModelManager`
(GPU/VRAM); under GPU-first placement the two **coordinate at admission**: the `ModelManager`
fit-tests each spawn against the VRAM soft-cap headroom and places the **whole** subagent on GPU
(`-ngl 99`, bigger models up to ~4B when it fits) or falls back to CPU-only (`-ngl 0`), with no
partial GPU+CPU straddle. The dedicated CPU `llama-server` sidecar (increment 3/4) becomes the
**fallback** path, not the only one. The `SubagentScheduler` also gains a soft CPU/RAM admission
budget for per-container resource caps (no hard WSL limits). This revision, with the
resource-governance design and adversarially-verified WSL2 feasibility (there is no per-process
GPU-utilization cap on this stack), is **Slice 8.5 / ADR-0012**. The Slice 7 code (scheduler,
task store, spawn tool) is unchanged; the placement/admission layer above it grows.

## Addendum (2026-07-03): the cortex-driven GPU path was host-closed 2026-07-01

The remaining host-only half, the resident gemma-4-12B *deciding* to emit `spawn_subagents`
end to end ([runbook §3](../runbooks/subagents-cpu.md)), was validated and closed by the
**user on 2026-07-01**, closing Slice 7 with it. The closure was recorded at the time only in
the ROADMAP status/progress text (commit `42fb330`); this addendum is the ADR-side record,
added when the 2026-07-02 slice audit (`audit/slice-7.md`, which was a review artifact removed
after remediation; in git history through commit `96463aa`) flagged the ROADMAP-only
paper trail. No measurements were recorded beyond the closure itself. The
machinery measurements live in the increment-4 addendum above.

## Addendum (2026-07-14): one call's batch is capped at `MAX_SPAWN_BATCH`

The [ADR-0009 turn-wide addendum](ADR-0009-tools-mcp.md) made a spawned batch draw on the
spawning turn's one dispatch pool, so an `instructions` array could no longer buy an unbounded
number of external calls. It left the array itself unbounded, and named the gap: bounded in
dispatches, still unbounded in **model runs**.

The two really are different currencies, which is why the pool could not close this on its own.
A subagent that calls no tools spends nothing from the dispatch pool while still costing an
admission slot, a placement, and an inference. And `ResourceBudgetScheduler.admit` **queues**
rather than refuses (by design, ADR-0012: over budget, callers wait), so an array of fifty was
never an error the cortex could see. It was fifty inferences the turn sat through, two at a time
under the default CPU budget.

**Decision: a per-call cap, `MAX_SPAWN_BATCH = 8` in `spawn.py`.** An oversized batch is
**refused**, never truncated: silently dropping subtasks would hand the cortex an aggregate that
reads as complete, whereas an `is_error` result (trusted, our own message, the existing
bad-arguments contract) is something the model corrects by re-delegating in batches that fit. The
check sits **ahead of item parsing**, so an oversized array is refused without walking it and
before a single `SubagentTask` is stored or a single subagent placed. The cap is advertised
twice, as `maxItems` on the array (a bound a constrained decoder can enforce structurally) and as
prose in both descriptions (for a model that reads only those), so the runtime check is the
backstop rather than the first the cortex hears of it.

**Why per call, and not a turn-wide pool mirroring the dispatch budget.** The turn-wide addendum
argued for one number over a product of two constants, and that argument does not carry here,
because it was really about a factor that was *unbounded*: `MAX_TOOL_STEPS` multiplied by an
uncapped per-round call count. Both factors are now deliberate. A spawn costs a quarter of the
dispatch pool by default (`DEFAULT_SPAWN_COST`, ADR-0009 cost addendum), so a turn affords four
batches, and the turn's ceiling is a statable four times this cap. A user who reprices
`spawn_subagents` through `CORTEX_TOOLS_COSTS` moves that factor knowingly, which is the point of
having priced it. A closing turn-wide pool would also be worse behaviour: the first
oversized batch would end delegation for the rest of the turn, where a per-call refusal is
correctable. One property falls out of the composition rather than being designed: a refused
batch still costs its spawn price, because `stream_tool_loop` charges ahead of the dispatch, so
retry spam is itself bounded at four attempts.

**Why a code constant and not an env knob.** `CORTEX_SUBAGENTS_CPU_BUDGET` and friends tune what
this host can run *concurrently*, which is a deployment fact. How many subtasks one call may
*ask* for is a policy the composition root does not vary, so it lives beside `MAX_TOOL_DISPATCHES`
as a constant. Eight sits above plausible delegation (two to five parallel subtasks in practice)
and far below fan-out spam. A knob is recorded as deferred should a deployment ever want one.

CI-gated over the fakes at 100%, with three guards mutation-proven (each reverted individually
turns a distinct test red): the cap itself, its comparison (an off-by-one that would cost the
cortex its largest legitimate batch), and the advertised `maxItems`.

Remaining behind the same tool: a **`CORTEX_SUBAGENTS_MAX_BATCH` knob** if a host ever wants a
different ceiling, and a **cost-aware batch** (a cap in placements or estimated VRAM rather than
in items) if roster entries ever differ enough that eight of one is not eight of another.

## Addendum (2026-07-16): the "run concurrently" advertisement now states the measured trade-off

This ADR introduced the spawn tool's description, which told the cortex subagents "run
concurrently" and delegation was "worth parallelizing". The same-day admission-wall measurement
(ADR-0012) showed that framing overstates the wiring: same-model spawns serialize on the entry's
one backend lease, and only spreading across distinct roster models overlaps them. The advertised
text was tuned to match the measurement; the full record and the residual (the nudge's live
uptake, unverifiable on the 8 GB dev GPU) live at the
[ADR-0018 addendum](ADR-0018-heterogeneous-subagents.md), the ADR that owns the roster and the
per-item model choice. The tool's behavior (`asyncio.gather` over the batch) is unchanged.

## Addendum (2026-07-16): subagent progress rides a `ProgressSink` side channel to the overlay

The Risks section deferred surfacing per-subagent progress to the overlay ("Progress is reported
to the overlay via the `Converse` status stream, a later refinement"). It lands now, together with
the ADR-0022 "subagent tool-step surfacing" deferral, as **one side channel** that serves both.

**Two facts the deferral named, both confirmed against the code first.** (1) While a spawn runs,
the cortex turn's engine generator is suspended inside `await dispatcher.dispatch(...)` in
`tool_loop.py`, so `handle_turn` cannot yield a progress event of its own. (2) `SpawnSubagentsTool`
is built **once** (`build_subagents` in `wiring.run_from_env`, its `spawn_tool` folded into
`builtins`, which every per-stream `make_engine` reuses), so it holds no per-stream state and had
no way to address one turn's overlay. Both were verified in the tree before building.

**The channel: a `ProgressSink` port carried per call on the `TurnStamp`.** Of the two options the
deferral named (a per-stream tool, or carrying the stream's channel per call) this takes the
second. A new pure-core `ProgressSink` (`progress.py`, port-free so `tools.py` may depend on it,
`async emit(ToolActivity | StatusUpdate)`) rides the dispatch `TurnStamp` beside `budget` (another
live handle, `compare=False`). The engine stamps its stream's sink onto each dispatch; the shared
`SpawnSubagentsTool` reads it off `call.stamp.progress` per call and passes it to each
`SubagentRunner.run`, so the one built-once tool serves every stream with **no per-stream field to
leak across turns** (a test routes two sinks through one shared tool to prove the isolation).

**What it surfaces, and why it needs no guardrail pass.** `SpawnSubagentsTool` emits a
`StatusUpdate(state="delegating", "delegating N subtasks")` (the batch's scale) before the gather,
and the `SubagentRunner` maps each subagent's `ToolStep` onto the sink as a `ToolActivity` (the
prior deferral's "the subagent runner drops it" note becomes "maps it onto the sink when it has
one"). Every field is registry-authored (the matched `ToolSpec`) or brain-authored (a count), never
the model's call or untrusted content, so a tainted subagent's progress carries nothing injectable
and needs no guardrail pass, exactly the argument the cortex's own `ToolActivity` makes. The wording
is honest to the measured wiring (ADR-0012 admission-wall addendum): "delegating N subtasks", never
a parallelism claim same-model spawns do not deliver.

**The adapter is credit-balanced, not the confirmer's control path.** The real `SeamProgressSink`
puts onto the stream's output queue taking a buffer credit only when one is free, else dropping the
event (best-effort). A delegating turn emits many steps, so over-crediting like the confirmer would
drift the buffer bound; taking-and-releasing a credit per event keeps it exact, and dropping under
saturation never stalls the subagent behind a slow overlay. Event ordering is preserved because the
turn task is suspended in `dispatch` and puts nothing itself while the subagents run.

**No proto change.** The overlay already renders `ToolActivity` and `StatusUpdate` chips, so the
seam and the overlay reducer are untouched; the wire nothing-shows trap is avoided because the
consumer already exists. CI-gated at 100% over the fakes (`RecordingProgressSink`), with the
routing, the runner emission, the taint containment, the two-sink isolation, and the sink's
drop-under-saturation each mutation-proven; the end-to-end path (cortex spawns → subagent tool step
→ wire `ToolActivity`) is exercised over a real `converse()` stream. The bundled backlog entries
close in [subagents.md](../refinements/subagents.md) and
[email-confirmer.md](../refinements/email-confirmer.md).

## Addendum (2026-07-19): the nudge residual's "unverifiable on the 8 GB dev GPU" is struck

The 2026-07-16 addendum above hands the spontaneous-pick residual to
[ADR-0018](ADR-0018-heterogeneous-subagents.md) and describes it in passing as "unverifiable on the
8 GB dev GPU". That card runs the real cortex (`-ngl 99 --ctx-size 4096 --parallel 1`, projector
loaded, 7715 of 8188 MiB, [ADR-0029](ADR-0029-vision-screen-capture.md) on 2026-07-17), so the
uptake probe is agent-side work rather than host work. The full correction, and what stays
host-side, is at the ADR-0018 addendum of the same date.

No code changed here; this is a records correction at the origin ADR.
