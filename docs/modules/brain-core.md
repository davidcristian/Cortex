# brain/packages/core (`cortex_core`)

**Purpose.** The brain's pure core: domain types, ports, and application logic. Routing,
the "handle a user turn" use-case, the memory remember/recall use-case, and tool dispatch
live here now; handoff orchestration joins them in a later slice. No I/O, ever. This is
the hexagon's center.

**Public contract** (everything importable from `cortex_core`; `__all__` is the API):

Routing (Slice 1):

- `Tier` is an enum of model tiers: `CORTEX`, `SUBAGENT`, `BRAIN` (string values).
- `RoutingHints` is a frozen dataclass: `explicit_tier: Tier | None = None`,
  `needs_deep_reasoning: bool = False`, `is_narrow_delegable: bool = False`.
- `route_turn(hints: RoutingHints) -> Tier` is a pure decision with strict precedence:
  explicit override → deep reasoning (`BRAIN`) → narrow delegable (`SUBAGENT`) →
  default `CORTEX`.

Conversation domain (Slice 3):

- `Role` is an enum: `USER`, `ASSISTANT`, `SYSTEM` (string values). `SYSTEM` carries
  engine-injected context (recalled memories, ADR-0008) and is never persisted to a
  session's history. It is derived fresh per turn and handed only to the model.
- `Message` is a frozen dataclass: `role: Role`, `text: str`, `at: datetime`,
  `turn_id: str`. Rejects naive `at` with `ValueError`, since externalized state must carry
  its timezone. `turn_id` ties a user message to the assistant reply it produced.
- `TextDelta(text)` / `TurnCompleted(turn_id, full_text)` are frozen domain events;
  `TurnEvent` is their union (the orchestrator maps them onto the proto's
  `ServerEvent` at the seam).

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

Ports (`typing.Protocol`; failures cross them only as the typed errors below):

- `SessionStore` provides `async append(session_id, message) -> None`,
  `async history(session_id) -> Sequence[Message]` (append order; empty when unknown).
  The source of truth for conversation state; survives swaps and restarts.
- `InferenceBackend` provides `stream(model, messages) -> AsyncIterator[str]`: one stateless
  streamed completion. `model` is a logical id (ADR-0004), never a path.
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
- `Clock` provides `now() -> datetime`, always tz-aware. The core's only time source.
- `SessionStoreError` / `InferenceError` / `ModelManagerError` (+ its
  `ModelUnavailableError`) / `MemoryStoreError` / `EmbedderError` / `ToolError` (+ its
  `ToolNotFoundError`) are typed errors; adapters wrap their backend's failures into these
  with the cause chained.

Use-case:

- `TurnEngine(store, backend, clock, *, cortex_model=DEFAULT_CORTEX_MODEL, memory=None,
  turn_id_factory=<uuid4>)` is pure orchestration over the ports.
  `handle_turn(session_id, text)` is an async generator: routes via
  `route_turn(RoutingHints())` (always `CORTEX` in this slice; the tier keys the model
  choice), builds the user `Message` (clock + turn-id factory), appends it to the
  store, streams deltas from the backend over the FULL history, yields `TextDelta`
  per delta, then persists the assistant `Message` and yields one `TurnCompleted`.
  Cancellation semantics: closing the event stream mid-generation (`aclose()`) keeps
  the persisted user message, does NOT persist the partial assistant text, and closes
  the abandoned backend stream. Backend failures surface as `InferenceError` after the
  user message was persisted.
  Memory (optional, ADR-0008): when a `MemoryRecaller` is injected, before inference the
  engine recalls the top `DEFAULT_RECALL_K` (5) memories for the user text and, if any,
  prepends them as a `Role.SYSTEM` message to the history the backend sees. It is ephemeral,
  never stored. After completion it records the `User: …\nAssistant: …` exchange to
  memory. With `memory=None` (the default) the turn behaves exactly as before.
- `DEFAULT_CORTEX_MODEL` is the logical id `"cortex"`. Deployments override it via
  `CORTEX_MODEL_CORTEX`, read by the composition root (orchestrator), never here.
- `MemoryRecaller(store, embedder, clock, *, id_factory=<uuid4>)` is the memory v1 use-case
  (ADR-0008). `record(text)` embeds `text`, persists a `MemoryRecord` (id from the factory,
  `at` from the clock, embedding from the embedder), and returns it; `recall(query, *, k)`
  embeds `query` and returns the store's top-`k` `ScoredMemory`. Stateless over the store:
  every memory lives in `MemoryStore`, so recall is identical across restarts and swaps.
  Wired into `TurnEngine` (retrieve-into-context, record-at-turn-end) when injected.
- `ToolDispatcher(registry, audit, clock)` is the tool-dispatch use-case (ADR-0009).
  `dispatch(call)` runs `call` through the `ToolRegistry`, writes exactly one
  `ToolInvocation` to the `ToolAuditSink` (success or failure), and returns the
  `ToolResult`; a `ToolError` from the registry becomes an `is_error` result so the loop
  keeps going and the model is told. Stateless over the ports; the turn-engine loop that
  drives it lands in Slice 6 increment 2.

Reference implementations (pure, shipped in core; the runtime wiring until Slice 4):

- `InMemorySessionStore` is a dict-backed `SessionStore`; contract-test twin of the Redis
  adapter (`cortex_session`), intentionally does not survive a restart.
- `EchoInferenceBackend` is the scripted fake: for a history with `n` user messages
  (including the current one, counted from the store-backed history alone) whose
  latest user text is `T`, streams exactly `"reply {n}: {T}"` in three deltas; raises
  `InferenceError` if the history has no user message. Because `n` comes from the
  store, it keeps counting across a process restart. That is observable state survival.
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
- `SystemClock` provides tz-aware UTC `now()`.

**Invariants.**
- Pure and deterministic: no I/O, no adapter or framework imports, stdlib only.
- The engine is a stateless function over the store: nothing about a conversation
  outlives `handle_turn` except what `SessionStore` holds (the one hard rule).
- The assistant message is persisted if and only if `TurnCompleted` is emitted.
- Fully typed (PEP 561 `py.typed` ships with the package); pyright strict clean.
- 100% line+branch covered by behavior tests in `tests/` (cancellation and failure
  paths included).

**Dependencies.** Python stdlib only.
