# brain/packages/core (`cortex_core`)

**Purpose.** The brain's pure core: domain types, ports, and application logic. Routing
and the "handle a user turn" use-case live here now; handoff orchestration, memory
policy, and tool dispatch decisions join them in later slices. No I/O, ever. This is
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

- `Role` is an enum: `USER`, `ASSISTANT` (string values `"user"`/`"assistant"`).
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

Ports (`typing.Protocol`; failures cross them only as the typed errors below):

- `SessionStore` provides `async append(session_id, message) -> None`,
  `async history(session_id) -> Sequence[Message]` (append order; empty when unknown).
  The source of truth for conversation state; survives swaps and restarts.
- `InferenceBackend` provides `stream(model, messages) -> AsyncIterator[str]`: one stateless
  streamed completion. `model` is a logical id (ADR-0004), never a path.
- `ModelManager` provides `acquire(model) -> AbstractAsyncContextManager[ModelLease]`: owns the
  GPU, queues for access, yields a `ModelLease`; leaving the block releases it to the
  next waiter. Consumed by the inference adapter (and, later, the handoff use-case).
- `Clock` provides `now() -> datetime`, always tz-aware. The core's only time source.
- `SessionStoreError` / `InferenceError` / `ModelManagerError` (+ its
  `ModelUnavailableError`) are typed errors; adapters wrap their backend's failures into
  these with the cause chained.

Use-case:

- `TurnEngine(store, backend, clock, *, cortex_model=DEFAULT_CORTEX_MODEL,
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
- `DEFAULT_CORTEX_MODEL` is the logical id `"cortex"`. Deployments override it via
  `CORTEX_MODEL_CORTEX`, read by the composition root (orchestrator), never here.

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
