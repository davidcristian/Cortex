# brain/packages/core (`cortex_core`)

**Purpose.** The brain's pure core: domain types, ports, and application logic. Routing,
the "handle a user turn" use-case, the memory remember/recall use-case, tool dispatch, and
subagent delegation live here now; handoff orchestration joins them in a later slice. No I/O,
ever. This is the hexagon's center. The bounded infer↔tool loop is one shared function
(`tool_loop.stream_tool_loop`) that both the cortex turn and each subagent run (ADR-0010).

**Public contract** (everything importable from `cortex_core`; `__all__` is the API):

Routing (Slice 1):

- `Tier` is an enum of model tiers: `CORTEX`, `SUBAGENT`, `BRAIN` (string values).
- `RoutingHints` is a frozen dataclass: `explicit_tier: Tier | None = None`,
  `needs_deep_reasoning: bool = False`, `is_narrow_delegable: bool = False`.
- `route_turn(hints: RoutingHints) -> Tier` is a pure decision with strict precedence:
  explicit override → deep reasoning (`BRAIN`) → narrow delegable (`SUBAGENT`) →
  default `CORTEX`.

Conversation domain (Slice 3):

- `Role` is an enum: `USER`, `ASSISTANT`, `SYSTEM`, `TOOL` (string values). `SYSTEM` carries
  engine-injected context (recalled memories, ADR-0008); `TOOL` carries a tool result fed
  back to the model (ADR-0009). Both (and the in-turn tool-call messages) are derived per
  turn and handed only to the model, never persisted to a session's history in v1.
- `Message` is a frozen dataclass: `role: Role`, `text: str`, `at: datetime`, `turn_id: str`,
  plus the optional tool fields `tool_calls: tuple[ToolCall, ...] = ()` (set on an assistant
  message that asked to run tools) and `tool_call_id: str | None = None` (set on a `TOOL`
  result). Rejects naive `at` with `ValueError`, since externalized state must carry its
  timezone. `turn_id` ties a user message to the assistant reply it produced.
- `TextDelta(text)` / `TurnCompleted(turn_id, full_text)` are frozen domain events;
  `TurnEvent` is their union (the orchestrator maps them onto the proto's `ServerEvent`).
- `TextChunk(text)` carries one streamed text delta from a backend; `InferenceEvent` is the union
  `TextChunk | ToolCall`, what an `InferenceBackend` yields (ADR-0009).

Model management (Slice 4, ADR-0007):

- `ModelLease` is a frozen dataclass: `endpoint: str`. A live claim on the GPU for one
  model, valid only inside the `acquire(...)` block that yields it; `endpoint` is the
  base URL of that model's `llama-server`.

Memory domain (Slice 5, ADR-0008):

- `MemoryRecord` is a frozen dataclass: `id: str`, `text: str`, `embedding: tuple[float, ...]`,
  `at: datetime`. One durable memory; rejects naive `at` with `ValueError` (memory outlives
  every process). The caller fills every field, leaving the store a pure translator.
- `ScoredMemory` is a frozen dataclass: `record: MemoryRecord`, `score: float`. A retrieval
  hit and its similarity (higher = closer).

Tool domain (Slice 6, ADR-0009; untrusted-content fields Slice 6.5, ADR-0013):

- `Trust` is an enum `TRUSTED` / `UNTRUSTED` (string values): the provenance of a tool result's
  content (ADR-0013). `UNTRUSTED` is third-party content framed as data; `TRUSTED` is
  system-generated. The default is `UNTRUSTED` everywhere (fail-closed).
- `ToolSpec` is a frozen dataclass: `name: str`, `description: str`,
  `parameters: Mapping[str, Any]` (the JSON Schema the model fills; passed through verbatim,
  never interpreted by the core), `gated: bool = False` (an irreversible/outbound action that
  needs confirmation once the turn read untrusted content, but no tool sets it today). What a tool
  advertises.
- `ToolCall` is a frozen dataclass: `id: str`, `name: str`, `arguments: Mapping[str, Any]`. A
  model's request to run one tool; `id` correlates it with its `ToolResult`.
- `ToolResult` is a frozen dataclass: `call_id: str`, `content: str`, `is_error: bool = False`,
  `trust: Trust = Trust.UNTRUSTED`. The outcome fed back to the model; `is_error` marks a tool
  (or dispatch) failure; `trust` is the content's provenance (fail-closed default), read by the
  loop to fence untrusted content and mark taint.
- `ToolInvocation` is a frozen dataclass: `name`, `arguments`, `ok: bool`, `detail: str`,
  `at: datetime` (tz-aware, rejects naive), `trust: Trust = Trust.UNTRUSTED` (the provenance
  audit trail). One audit-trail line.
- `ConfirmationRequest` is a frozen dataclass: `tool_name: str`, `arguments: Mapping[str, Any]`,
  `reason: str`. What the dispatcher hands the `Confirmer` to approve a gated call out of band.

Subagent domain (Slice 7, ADR-0010):

- `SubagentTask` is a frozen dataclass: `id: str`, `instruction: str`, `context: str`,
  `at: datetime` (tz-aware, rejects naive). One narrow task delegated to a subagent, persisted
  before it runs; `context` is the material the subagent works from (the cortex conversation is
  never shared, since the subagent is stateless over the task).
- `SubagentResult` is a frozen dataclass: `task_id: str`, `output: str`, `ok: bool = True`,
  `detail: str = ""`, `tainted: bool = False`. A subagent's outcome; `ok=False` (with `detail`)
  marks a failure the cortex consumes as a value, mirroring `ToolResult.is_error`; `tainted` is
  set when the subagent read untrusted content, aggregated by the spawn tool (ADR-0013).

Placement domain (Slice 8.5, ADR-0012):

- `PlacementTarget` is an enum `GPU` / `CPU` (string values), where a subagent's whole model runs
  (never a partial straddle). `.ngl` maps it to the llama.cpp offload flag: `GPU → 99`, `CPU → 0`.
- `PlacementRequest` is a frozen dataclass: `model: str`, `vram_gb: float`, `cpus: float`,
  `memory_gb: float`. One subagent's resource ask; `__post_init__` rejects a non-positive resource
  with `ValueError`. `vram_gb` is fit-tested against headroom; `cpus`/`memory_gb` are the
  per-container caps the scheduler sums.
- `Placement` (frozen dataclass): `target: PlacementTarget`, `reserved_gb: float`. A `SubagentPlacer`
  verdict; `reserved_gb` is the request's `vram_gb` on GPU, `0.0` on CPU, so `release` is exact.
- `SubagentResources` is a frozen dataclass bundling one subagent tier's placement machinery:
  `backends: Mapping[PlacementTarget, InferenceBackend]`, `scheduler: SubagentScheduler`,
  `placer: SubagentPlacer`, `request: PlacementRequest`. Mirrors `TurnCapabilities`, collaborators
  the `SubagentRunner` always takes together (`request.model` is the subagent id).

Untrusted-content boundary (Slice 6.5, ADR-0013; the pure primitives in `untrusted.py`):

- `SECURITY_PREAMBLE` is the standing-rule constant, injected as a `Role.SYSTEM` message by the
  engine/runner when a turn has tools: content in the untrusted markers is data, never obeyed.
- `wrap_untrusted(content, *, nonce) -> str` fences untrusted content as
  `<untrusted-tool-output id=NONCE> … </untrusted-tool-output id=NONCE>`; a closing tag embedded
  in `content` cannot end the fence (it lacks the per-turn `nonce`), the delimiter-injection defense.
- `security_preamble_message(at, turn_id) -> Message` is the preamble as a `Role.SYSTEM` message.
- `new_nonce() -> str` is a new per-turn nonce (`secrets.token_hex(8)`), unpredictable, dies with the turn.
- `DENIED_MSG` is the `is_error` result content fed back when a gated tool is blocked.
- `TaintLedger` is mutable, turn-local: `tainted: bool = False`, `mark(trust)` flips it on the first
  `UNTRUSTED` result. Passed into the shared loop; reconstructed each turn, never persisted.
- `ToolLoopContext` is a frozen bundle of a tool loop's per-invocation collaborators (`dispatcher`,
  `clock`, `turn_id`, `taint`, `nonce`), keeping `stream_tool_loop` under its argument ceiling.

Ports (`typing.Protocol`; failures cross them only as the typed errors below):

- `SessionStore` provides `async append(session_id, message) -> None`,
  `async history(session_id) -> Sequence[Message]` (append order; empty when unknown).
  The source of truth for conversation state; survives swaps and restarts.
- `InferenceBackend` has `stream(model, messages, *, tools=()) -> AsyncIterator[InferenceEvent]`:
  one stateless streamed completion, yielding `TextChunk` deltas interleaved with `ToolCall`s
  the model makes from the offered `tools` (ADR-0009). `model` is a logical id (ADR-0004).
- `ModelManager` provides `acquire(model) -> AbstractAsyncContextManager[ModelLease]`: owns the
  GPU, queues for access, yields a `ModelLease`; leaving the block releases it to the
  next waiter. Consumed by the inference adapter (and, later, the handoff use-case).
- `Embedder` provides `async embed(text) -> Sequence[float]`: one stateless call, text to vector.
  Dimension is fixed by the deployment's model (ADR-0008); the core assumes no value.
- `MemoryStore` provides `async add(record) -> None`, `async search(embedding, *, k) ->
  Sequence[ScoredMemory]` (top-`k` by similarity, most-similar first, over ALL memories, since
  v1 is one global space). Durable, cross-session; the caller builds each record.
- `ToolRegistry` has `async describe_tools() -> Sequence[ToolSpec]` (advertise the tools),
  `async invoke(call) -> ToolResult` (run one call; `is_error` reflects a tool-level
  failure). An unknown tool or a transport failure raises `ToolError`
  (`ToolNotFoundError` for the name). The dispatcher, not the registry, turns that into an
  error result.
- `ToolAuditSink` has `async record(invocation) -> None`: every dispatched call is written
  here, success or failure (the AGENTS.md audit requirement).
- `Confirmer` has `async confirm(request: ConfirmationRequest) -> bool` (ADR-0013): approves or
  denies a gated tool call out of band (the overlay, later). The human's decision, never the
  model's; a missing confirmer denies (fail-closed). The real adapter arrives with the first
  gated tool (Slice 9/10).
- `TaskStore` has `async put_task(task) -> None`, `async get_task(task_id) -> SubagentTask | None`,
  `async put_result(result) -> None`, `async get_result(task_id) -> SubagentResult | None`. The
  hot store (Redis) a subagent is a stateless function over: task and result live here, never in
  a model process (ADR-0010). Unknown ids return `None`.
- `SubagentPlacer` has `place(request) -> Placement`, `release(placement) -> None` (both sync): the
  VRAM-budget accountant (ADR-0012). `place` fit-tests `request.vram_gb` against the live headroom
  (`soft_cap − cortex_reservation − placed`), reserving it on GPU or spilling to CPU; `release`
  frees it. The GPU/VRAM contract, separate from `ModelManager`'s lease and `SubagentScheduler`'s
  budget. The three compose at `SubagentRunner`.
- `SubagentScheduler` (`admit(request) -> AbstractAsyncContextManager[None]`): a soft two-dimensional
  CPU/RAM budget for spawns (yields once the request's `cpus`/`memory_gb` fit the summed targets,
  queues over budget, releases both on exit). A charge larger than the whole budget raises
  `ValueError`. A counting budget, not the GPU lease (ADR-0012, revising ADR-0010).
- `Clock` provides `now() -> datetime`, always tz-aware. The core's only time source.
- `SessionStoreError` / `InferenceError` / `ModelManagerError` (+ its
  `ModelUnavailableError`) / `MemoryStoreError` / `EmbedderError` / `ToolError` (+ its
  `ToolNotFoundError`) / `TaskStoreError` are typed errors; adapters wrap their backend's failures
  into these with the cause chained.

Use-case:

- `TurnEngine(store, backend, clock, *, cortex_model=DEFAULT_CORTEX_MODEL,
  capabilities=TurnCapabilities(), turn_id_factory=<uuid4>)` is pure orchestration over the
  ports. `handle_turn(session_id, text)` is an async generator: routes via
  `route_turn(RoutingHints())` (always `CORTEX` in this slice; the tier keys the model
  choice), builds the user `Message` (clock + turn-id factory), appends it to the store,
  runs the inference↔tool loop over ALL of the stored history, unless a
  `capabilities.window` selects the newest slice (ADR-0014; persistence untouched),
  yields `TextDelta` per streamed chunk, then persists the assistant `Message` and
  yields one `TurnCompleted`.
  Cancellation semantics: closing the event stream mid-generation (`aclose()`) keeps
  the persisted user message, does NOT persist the partial assistant text, and closes
  the abandoned backend stream. Backend failures surface as `InferenceError` after the
  user message was persisted.
  Memory (optional, ADR-0008): when `capabilities.memory` is set, before inference the
  engine recalls the top `DEFAULT_RECALL_K` (5) memories for the user text and, if any,
  prepends them as a `Role.SYSTEM` message to the context the backend sees. It is ephemeral,
  never stored. After completion it records the `User: …\nAssistant: …` exchange to memory
  **unless the turn read untrusted content**, in which case nothing is recorded (ADR-0013), so
  every stored memory stays safe to recall as trusted.
  Tools (optional, ADR-0009): when `capabilities.tools` is set, the engine prepends the
  untrusted-content `SECURITY_PREAMBLE` (ADR-0013) and runs the shared `stream_tool_loop` with
  that `ToolDispatcher` and a fresh per-turn `TaintLedger`. The loop advertises the registry's
  tools each step, dispatches a step's `ToolCall`s (audited, gated), feeds results back as an
  `ASSISTANT`-with-`tool_calls` message plus (untrusted-fenced) `Role.TOOL` results, and re-infers
  up to `MAX_TOOL_STEPS` rounds. These tool messages are in-turn only (never persisted in v1). With
  a bare `TurnCapabilities()` (the default) the turn behaves exactly as Slice 3.
- `TurnCapabilities(memory=None, tools=None, window=None)` is a frozen bundle of the optional
  per-turn collaborators (a `MemoryRecaller`, a `ToolDispatcher`, and a `HistoryWindow`),
  keeping the engine within its DI ceiling.
- `HistoryWindow` (protocol, `windowing.py`) / `CharBudgetHistoryWindow(max_chars)` are the
  session-history windowing seam and its shipped policy (ADR-0014). `select(history)`
  returns the slice one turn sends to the model: `CharBudgetHistoryWindow` keeps the newest
  whole turns (grouped by consecutive `turn_id`) whose summed text length fits `max_chars`,
  as a contiguous tail, with turns kept or dropped whole, the walk stopping at the first
  overflow, the newest turn always kept even oversized (the current user message must reach
  the model). Characters approximate tokens (~4 chars/token) so the core needs no tokenizer.
  Applied at inference-message assembly only. The store keeps the full history.
  `max_chars < 1` raises `ValueError` (`0` as an off switch lives in the wiring, not here).
- `stream_tool_loop(backend, model, working, context: ToolLoopContext)` (in `tool_loop`)
  is the bounded infer↔tool loop shared by `TurnEngine` and `SubagentRunner` (ADR-0010): an
  async generator yielding assistant text deltas, mutating `working` in place with the tool-call
  and `Role.TOOL` result messages; ends on a tool-free step, a `None` dispatcher, or
  `MAX_TOOL_STEPS` (8) rounds. It draws the untrusted boundary (ADR-0013): each call is dispatched
  with the turn's `tainted` state and the tool's `gated` flag (so a gated call on a tainted turn is
  confirmed), its result marks `context.taint`, and an `UNTRUSTED` result is fenced by
  `wrap_untrusted` before it re-enters `working`. `MAX_TOOL_STEPS` and `ToolLoopContext` are here.
- `DEFAULT_CORTEX_MODEL` is the logical id `"cortex"`. Deployments override it via
  `CORTEX_MODEL_CORTEX`, read by the composition root (orchestrator), never here.
- `MemoryRecaller(store, embedder, clock, *, id_factory=<uuid4>)` is the memory v1 use-case
  (ADR-0008). `record(text)` embeds `text`, persists a `MemoryRecord` (id from the factory,
  `at` from the clock, embedding from the embedder), and returns it; `recall(query, *, k)`
  embeds `query` and returns the store's top-`k` `ScoredMemory`. Stateless over the store:
  every memory lives in `MemoryStore`, so recall is identical across restarts and swaps.
  Wired into `TurnEngine` (retrieve-into-context, record-at-turn-end) when injected.
- `ToolDispatcher(registry, audit, clock, *, confirmer=None)` is the turn's tool gateway and
  capability gate (ADR-0009/0013). `dispatch(call, *, tainted=False, gated=False)` runs `call`
  through the `ToolRegistry`, writes exactly one `ToolInvocation` (with the result's `trust`) to
  the `ToolAuditSink`, and returns the `ToolResult`; a `ToolError` becomes a `TRUSTED` `is_error`
  result (our own message, so it neither frames nor taints). A `gated` tool on a `tainted` turn is
  confirmed via the `Confirmer` first, and a denial (including the fail-closed `confirmer=None`
  default) returns `DENIED_MSG` **without invoking the tool**, audited as a block. `describe_tools()`
  passes through to the registry. Stateless over the ports; the loop drives it.
- `SubagentRunner(store, resources, clock, *, tools=None)` is a subagent's body (ADR-0010/0012), a
  stateless function over the `TaskStore`. `run(task_id)` **admits** against the scheduler's CPU/RAM
  budget (outer, may wait), **places** on GPU or CPU against the VRAM budget (inner, synchronous),
  routes to `resources.backends[placement.target]`, loads the `SubagentTask` **by id** (never from
  cortex memory, with a missing task an `ok=False` "task not found" result), runs `stream_tool_loop`
  on `resources.request.model` with its optional tool subset (instruction as the user ask, `context`
  as a `Role.SYSTEM` message; a tools-enabled subagent also gets the `SECURITY_PREAMBLE` and its own
  `TaintLedger`, ADR-0013), persists + returns a `SubagentResult` carrying `tainted` from that ledger,
  and always releases the VRAM in a `finally`. A mid-stream `InferenceError` becomes an `ok=False`
  result carrying the partial text. Tools-enabled but not given the delegation tool, so fan-out is
  depth-1.
- `SpawnSubagentsTool(runner, store, clock, *, task_id_factory=<uuid4>)` is the built-in
  `spawn_subagents` tool (`SPAWN_TOOL_NAME`), the cortex's delegation primitive (ADR-0010). Its
  `spec` advertises `instructions: string[]`; `invoke(call)` validates them (bad input → an
  `is_error` result, not a raise), persists one `SubagentTask` each, runs the `SubagentRunner`s
  **concurrently** (bounded by the scheduler), and returns one aggregated `ToolResult`, with a
  `[subagent N] …` block per subtask, failures shown inline. The aggregate is `UNTRUSTED` iff any
  subagent was tainted, so a subagent that read a malicious file taints the cortex through the
  normal result path (ADR-0013). A `BuiltinTool` (`.spec` + async `invoke`), registered in a
  `CompositeToolRegistry`.
- `CompositeToolRegistry(builtins, remote=None)` is a `ToolRegistry` merging built-in tools with
  an optional remote (MCP) registry (ADR-0010). `describe_tools` advertises every built-in then
  the remote tools none shadows; `invoke` routes by name, built-ins first, else the remote, else
  `ToolNotFoundError`. Duplicate built-in names raise `ValueError` at construction. The
  internal-tool seam (ADR-0001 Q2) the body's OS actions (Slices 9-10) will reuse. `BuiltinTool`
  is the protocol it advertises/invokes.
- `AggregateToolRegistry(registries)` is a `ToolRegistry` over several registries (ADR-0009
  refinements addendum), letting the filesystem and email sidecars coexist behind the one port.
  `describe_tools` unions in registry order, deduplicating **first-wins** (construction order is
  precedence under the composite's shadowing rule; a later duplicate is neither advertised nor
  invokable); `invoke` routes to the first registry *currently* advertising the name, resolved
  by a live `describe_tools` walk (no cached routing, so a tool dropped server-side mid-turn
  fails closed as `ToolNotFoundError`). A listing failure anywhere propagates as `ToolError`
  (one dead sidecar is loud, never a silently smaller tool set, unless that sidecar is
  explicitly marked optional, below). An empty registry sequence raises `ValueError` at
  construction.
- `SkipUnavailableToolRegistry(inner, *, name, report)` marks one registry optional: the
  skip-and-report degraded mode (ADR-0009 degraded-mode addendum). A `describe_tools`
  failure (`ToolError`) becomes an empty advertisement plus one `report(name, error)` call, and
  the reporter is mandatory, so skipping cannot be silent, and it fires on every walk. Only
  discovery is softened: `invoke` delegates untouched (execution still fails loudly); via an
  aggregate, a dead sidecar's tools are unadvertised and fail closed as `ToolNotFoundError`.
- `FilteredToolRegistry(inner, *, allow)` is a `ToolRegistry` restricted to an allowlist of names
  (ADR-0009 refinements addendum, to stop advertising the write tools a read-only mount can only
  `EROFS`). `describe_tools` intersects the inner advertisement with `allow` (inner order kept);
  `invoke` refuses any other name as `ToolNotFoundError`, so the filter is a real layer, not
  advisory, though it only *restricts*, never grants (an allowlisted name the inner lacks stays
  unadvertised and surfaces the inner not-found). An empty allowlist raises `ValueError`.

Reference implementations (pure, shipped in core; the runtime wiring until Slice 4):

- `InMemorySessionStore` is a dict-backed `SessionStore`; contract-test twin of the Redis
  adapter (`cortex_session`), intentionally does not survive a restart.
- `EchoInferenceBackend` is the scripted fake: for a history with `n` user messages
  (including the current one, counted from the store-backed history alone) whose
  latest user text is `T`, streams exactly `"reply {n}: {T}"` as three `TextChunk`s
  (tool-independent, since it never calls a tool); raises `InferenceError` if the history has no
  user message. Because `n` comes from the store, it keeps counting across a process
  restart. That is observable state survival.
- `SingleResidentModelManager(resident_model, endpoint)` is the `ModelManager` v1
  (ADR-0007 d3): pure policy, no I/O. `acquire` serializes callers with an
  `asyncio.Lock` (its waiter queue is the "queue API") and yields a `ModelLease` for the
  `endpoint`; acquiring any model other than `resident_model` raises
  `ModelUnavailableError` (v1 performs no swap, since that lands in Slice 11). Lives in the
  core because it does no I/O; the process-lifecycle adapter arrives later behind the
  same port.
- `InMemoryMemoryStore` is a list-backed `MemoryStore` ranking by cosine similarity in Python;
  behavioral twin of the pgvector adapter (Slice 5 host half) behind the same contract. A
  zero-magnitude vector scores 0.0. Does not survive a restart, by design.
- `HashEmbedder(dimension=16)` is a deterministic, I/O-free `Embedder`: identical text always
  yields the identical vector (so a stored memory is its own strongest cosine match), distinct
  text a distinct vector. Carries no semantics. It is the CI/tests stand-in for the real nomic
  adapter (Slice 5 host half). Never emits an all-zero vector.
- `InMemoryToolRegistry({name: (spec, handler)})` is a dict-backed `ToolRegistry`; contract
  twin of the MCP adapter (Slice 6). A handler maps call arguments to result text; `invoke`
  raises `ToolNotFoundError` for an unknown name. No server, fully deterministic.
- `RecordingAuditSink` is a `ToolAuditSink` that keeps invocations in a list (`.records`) so
  tests can assert the audit trail.
- `RecordingConfirmer(*, answer)` is a `Confirmer` returning a fixed `answer` and recording each
  `ConfirmationRequest` in `.requests`, so gate tests can assert what was confirmed (ADR-0013).
- `InMemoryTaskStore` is a dict-backed `TaskStore`; contract twin of the Redis adapter (Slice 7
  CI half). Unknown ids return `None`. Does not survive a restart, by design.
- `VramBudgetPlacer(*, soft_cap_gb, cortex_reservation_gb)` is the `SubagentPlacer` v1 (ADR-0012):
  pure GPU-first policy, no I/O. `place` returns a GPU `Placement` (reserving `vram_gb`) when the ask
  fits `soft_cap − cortex_reservation − placed`, else a CPU one (reserving nothing); `release` credits
  it back. Sync and lock-free (single-threaded asyncio atomicity), so the concurrent batch races the
  ledger correctly. The ledger is live-resource state, rebuilt from zero. It is never durable state.
- `ResourceBudgetScheduler(cpu_budget, mem_budget_gb)` is `SubagentScheduler` v2 (ADR-0012): pure
  policy over an `asyncio.Condition`. `admit(request)` reserves the request's `cpus`/`memory_gb` while
  both summed reservations stay within targets, queuing (with `notify_all` on release) otherwise; a
  non-positive budget or a charge exceeding the whole budget raises `ValueError`. Replaces Slice 7's
  `ConcurrencyScheduler` (the bare counting semaphore), which the two-dimensional budget subsumes.
- `SystemClock` provides tz-aware UTC `now()`.

**Invariants.**
- Pure and deterministic: no I/O, no adapter or framework imports, stdlib only.
- The engine is a stateless function over the store: nothing about a conversation
  outlives `handle_turn` except what `SessionStore` holds (the one hard rule). Likewise a
  subagent is a stateless function over the `TaskStore`. `SubagentRunner` reads the task by
  id and persists the result, holding nothing between calls.
- The assistant message is persisted if and only if `TurnCompleted` is emitted.
- The untrusted boundary is fail-closed (ADR-0013): `trust`/provenance defaults to `UNTRUSTED`,
  so unstamped content is framed as data; the `TaintLedger` is turn-local, reconstructed each turn
  from the store + live tool results, never persisted (the one hard rule holds); a tainted turn is
  never recorded to memory, so recall stays trustworthy.
- Fully typed (PEP 561 `py.typed` ships with the package); pyright strict clean.
- 100% line+branch covered by behavior tests in `tests/` (cancellation and failure
  paths included).

**Dependencies.** Python stdlib only.
