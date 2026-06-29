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

Tool domain (Slice 6, ADR-0009):

- `ToolSpec` is a frozen dataclass: `name: str`, `description: str`,
  `parameters: Mapping[str, Any]` (the JSON Schema the model fills; passed through verbatim,
  never interpreted by the core). What a tool advertises.
- `ToolCall` is a frozen dataclass: `id: str`, `name: str`, `arguments: Mapping[str, Any]`. A
  model's request to run one tool; `id` correlates it with its `ToolResult`.
- `ToolResult` is a frozen dataclass: `call_id: str`, `content: str`, `is_error: bool = False`.
  The outcome fed back to the model; `is_error` marks a tool (or dispatch) failure.
- `ToolInvocation` is a frozen dataclass: `name`, `arguments`, `ok: bool`, `detail: str`,
  `at: datetime` (tz-aware, rejects naive). One audit-trail line.

Subagent domain (Slice 7, ADR-0010):

- `SubagentTask` is a frozen dataclass: `id: str`, `instruction: str`, `context: str`,
  `at: datetime` (tz-aware, rejects naive). One narrow task delegated to a subagent, persisted
  before it runs; `context` is the material the subagent works from (the cortex conversation is
  never shared, since the subagent is stateless over the task).
- `SubagentResult` is a frozen dataclass: `task_id: str`, `output: str`, `ok: bool = True`,
  `detail: str = ""`. A subagent's outcome; `ok=False` (with `detail`) marks a failure the
  cortex consumes as a value, mirroring `ToolResult.is_error`.

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
- `TaskStore` has `async put_task(task) -> None`, `async get_task(task_id) -> SubagentTask | None`,
  `async put_result(result) -> None`, `async get_result(task_id) -> SubagentResult | None`. The
  hot store (Redis) a subagent is a stateless function over: task and result live here, never in
  a model process (ADR-0010). Unknown ids return `None`.
- `SubagentScheduler` (`admit() -> AbstractAsyncContextManager[None]`): a bounded-concurrency CPU
  budget for spawns (yields a slot, queues over the cap). Distinct from `ModelManager`'s
  exclusive GPU lease. This is a counting budget, not a lock (ADR-0010).
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
  runs the inference↔tool loop over the FULL history, yields `TextDelta` per streamed
  chunk, then persists the assistant `Message` and yields one `TurnCompleted`.
  Cancellation semantics: closing the event stream mid-generation (`aclose()`) keeps
  the persisted user message, does NOT persist the partial assistant text, and closes
  the abandoned backend stream. Backend failures surface as `InferenceError` after the
  user message was persisted.
  Memory (optional, ADR-0008): when `capabilities.memory` is set, before inference the
  engine recalls the top `DEFAULT_RECALL_K` (5) memories for the user text and, if any,
  prepends them as a `Role.SYSTEM` message to the context the backend sees. It is ephemeral,
  never stored. After completion it records the `User: …\nAssistant: …` exchange to memory.
  Tools (optional, ADR-0009): when `capabilities.tools` is set, the engine runs the shared
  `stream_tool_loop` with that `ToolDispatcher`. The loop advertises the registry's tools each
  step, dispatches a step's `ToolCall`s (audited), feeds results back as an
  `ASSISTANT`-with-`tool_calls` message plus `Role.TOOL` results, and re-infers up to
  `MAX_TOOL_STEPS` rounds. These tool messages are in-turn only (never persisted in v1). With a
  bare `TurnCapabilities()` (the default) the turn behaves exactly as Slice 3.
- `TurnCapabilities(memory=None, tools=None)` is a frozen bundle of the optional per-turn
  collaborators (a `MemoryRecaller` and a `ToolDispatcher`), keeping the engine within its
  DI ceiling.
- `stream_tool_loop(backend, model, working, *, dispatcher, clock, turn_id)` (in `tool_loop`)
  is the bounded infer↔tool loop shared by `TurnEngine` and `SubagentRunner` (ADR-0010): an
  async generator yielding assistant text deltas, mutating `working` in place with the tool-call
  and `Role.TOOL` result messages; ends on a tool-free step, a `None` dispatcher, or
  `MAX_TOOL_STEPS` (8) rounds. `MAX_TOOL_STEPS` is defined here.
- `DEFAULT_CORTEX_MODEL` is the logical id `"cortex"`. Deployments override it via
  `CORTEX_MODEL_CORTEX`, read by the composition root (orchestrator), never here.
- `MemoryRecaller(store, embedder, clock, *, id_factory=<uuid4>)` is the memory v1 use-case
  (ADR-0008). `record(text)` embeds `text`, persists a `MemoryRecord` (id from the factory,
  `at` from the clock, embedding from the embedder), and returns it; `recall(query, *, k)`
  embeds `query` and returns the store's top-`k` `ScoredMemory`. Stateless over the store:
  every memory lives in `MemoryStore`, so recall is identical across restarts and swaps.
  Wired into `TurnEngine` (retrieve-into-context, record-at-turn-end) when injected.
- `ToolDispatcher(registry, audit, clock)` is the turn's tool gateway (ADR-0009).
  `dispatch(call)` runs `call` through the `ToolRegistry`, writes exactly one
  `ToolInvocation` to the `ToolAuditSink` (success or failure), and returns the
  `ToolResult`; a `ToolError` from the registry becomes an `is_error` result so the loop
  keeps going and the model is told. `describe_tools()` passes through to the registry so
  the engine advertises what it can dispatch. Stateless over the ports; `TurnEngine` drives
  the loop that calls it.
- `SubagentRunner(store, backend, scheduler, clock, *, subagent_model, tools=None)` is a
  subagent's body (ADR-0010), a stateless function over the `TaskStore`. `run(task_id)` admits
  against the `SubagentScheduler`'s CPU budget, loads the `SubagentTask` **by id** (never from
  cortex memory, since a missing task is an `ok=False` "task not found" result), runs
  `stream_tool_loop` on `subagent_model` with its optional tool subset (the instruction as the
  user ask, `context` as a `Role.SYSTEM` message), and persists + returns a `SubagentResult`. A
  mid-stream `InferenceError` becomes an `ok=False` result carrying the partial text, not an
  exception. Tools-enabled but not given the delegation tool, so fan-out is depth-1.

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
- `InMemoryTaskStore` is a dict-backed `TaskStore`; contract twin of the Redis adapter (Slice 7
  CI half). Unknown ids return `None`. Does not survive a restart, by design.
- `ConcurrencyScheduler(max_concurrency)` is the `SubagentScheduler` v1 (ADR-0010): pure policy
  over an `asyncio.Semaphore`. `admit()` grants one CPU slot and queues over the cap; a
  `max_concurrency < 1` raises `ValueError`. Lives in the core because it does no I/O. Hard
  RAM-ceiling rejection is a later refinement behind the port.
- `SystemClock` provides tz-aware UTC `now()`.

**Invariants.**
- Pure and deterministic: no I/O, no adapter or framework imports, stdlib only.
- The engine is a stateless function over the store: nothing about a conversation
  outlives `handle_turn` except what `SessionStore` holds (the one hard rule). Likewise a
  subagent is a stateless function over the `TaskStore`. `SubagentRunner` reads the task by
  id and persists the result, holding nothing between calls.
- The assistant message is persisted if and only if `TurnCompleted` is emitted.
- Fully typed (PEP 561 `py.typed` ships with the package); pyright strict clean.
- 100% line+branch covered by behavior tests in `tests/` (cancellation and failure
  paths included).

**Dependencies.** Python stdlib only.
